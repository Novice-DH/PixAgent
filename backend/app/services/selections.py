"""选区服务：Redis 瞬态存取 + 点选/笔刷两种选区语义 + 工具侧取遮罩。

选区存 Redis 不落数据库——选区是「正在进行的交互」不是实体：revision 一变
即废、会话结束即弃，24h TTL 让残留自灭。每次生成都落新遮罩资产（遮罩不可变、
追加=新遮罩）。与 Pub/Sub 共用 events.redis_client() 同一客户端与连接生命周期。
"""
import asyncio
import io
import json
import logging
import uuid
from typing import Any

import redis.exceptions
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.edits import mask as mask_edits
from app.edits import segment
from app.models.asset import Asset, AssetKind, AssetSource
from app.models.edit_session import EditSession
from app.services import assets as assets_service
from app.storage import get_object
from app.tools.context import current_document, flatten_session

logger = logging.getLogger(__name__)

KEY_PREFIX = "selection:"
SELECTION_TTL_SECONDS = 24 * 3600

STALE_CANVAS_MESSAGE = "画布已更新，请重新选择"  # 端点受理时 revision 不匹配 → 409
BLANK_MASK_MESSAGE = "选区为空"  # 分割结果为空 → 422
NO_SELECTION_MESSAGE = "请先点选或涂抹要修改的区域"  # 工具侧翻译为 ToolError
STALE_SELECTION_MESSAGE = "选区已过期，请重新选择"  # 工具执行时 revision 校验


class EmptySelection(Exception):
    """没有可用选区（存储缺失或显式资产不存在）——工具层翻译为 ToolError。"""


class BlankSelection(Exception):
    """分割结果为空（点在了背景上）——路由翻 422「选区为空」。"""


def _key(session_id: uuid.UUID) -> str:
    return f"{KEY_PREFIX}{session_id}"


async def get(session_id: uuid.UUID, revision: int) -> dict[str, Any] | None:
    """读取侧防护：payload 的 revision 不匹配（或无选区）返回 None——
    读到旧 payload 与读到没有选区同义。RedisError 向上传播（路由翻 503、
    工具侧按无选区收口）。"""
    raw = await events.redis_client().get(_key(session_id))
    if raw is None:
        return None
    payload = json.loads(raw)
    if payload.get("revision") != revision:
        return None
    return payload


async def clear(session_id: uuid.UUID) -> None:
    """选区一次性消费：DELETE 端点与局部工具成功后各走一次。"""
    await events.redis_client().delete(_key(session_id))


async def select_points(
    session: AsyncSession,
    row: EditSession,
    points: list[tuple[float, float]],
    *,
    append: bool,
) -> tuple[Asset, list[dict[str, Any]]]:
    """点选建区：flatten 画布 → 全部 markers 坐标一次性重分割 → 新遮罩 + 累积
    markers。追加是「重新分割全部点」不是「合并遮罩」——SAM 多点提示是联合
    语义（多点共同框定一个物体）。返回（遮罩资产, markers）。"""
    history: list[tuple[float, float]] = []
    if append:
        existing = await get(row.id, row.revision)
        if existing:
            history = [
                (float(m["x"]), float(m["y"])) for m in existing.get("markers") or []
            ]
    all_points = [*history, *points]
    source = await flatten_session(session, row)
    overlay = await _segment_to_overlay(source, all_points)
    asset = await assets_service.create_from_bytes(
        session, row.user_id, overlay, kind=AssetKind.mask, source=AssetSource.tool
    )
    markers = [
        {"index": index, "x": x, "y": y}
        for index, (x, y) in enumerate(all_points, start=1)
    ]
    await _store(row.id, row.revision, str(asset.id), markers)
    return asset, markers


async def select_strokes(
    session: AsyncSession,
    row: EditSession,
    strokes: list[list[tuple[float, float]]],
    *,
    radius: float,
) -> tuple[Asset, list[dict[str, Any]]]:
    """笔刷建区：现有遮罩（同 revision 有则取）为 base → 光栅化新笔迹并 union
    → 新遮罩。markers 透传保留（笔刷没有标点）。返回（遮罩资产, markers）。"""
    document = current_document(row)
    size = (document.width, document.height)
    base = None
    markers: list[dict[str, Any]] = []
    existing = await get(row.id, row.revision)
    if existing:
        mask_asset_id = existing.get("mask_asset_id")
        if mask_asset_id:
            asset = await assets_service.get_for_user(
                session, row.user_id, uuid.UUID(str(mask_asset_id))
            )
            if asset is not None:
                # 解码 + 重采样不进事件循环（与 overlay/rasterize 同一纪律）
                base = await asyncio.to_thread(
                    mask_edits.to_luma, await get_object(asset.storage_key), size
                )
        markers = existing.get("markers") or []
    pixel_strokes = [
        [(x * size[0], y * size[1]) for x, y in stroke] for stroke in strokes
    ]
    luma = await asyncio.to_thread(
        mask_edits.rasterize_strokes, size, pixel_strokes, radius=radius, base=base
    )
    overlay = await asyncio.to_thread(mask_edits.overlay_png, luma)
    asset = await assets_service.create_from_bytes(
        session, row.user_id, overlay, kind=AssetKind.mask, source=AssetSource.tool
    )
    await _store(row.id, row.revision, str(asset.id), markers)
    return asset, markers


async def mask_bytes(
    session: AsyncSession,
    user_id: uuid.UUID,
    record: dict[str, Any] | None,
    mask_asset_id: str | None,
) -> bytes:
    """工具侧取遮罩字节：显式 id 优先，缺省用当前存储（record 已按 revision
    匹配）；两者皆无抛 EmptySelection——局部工具翻译为 ToolError「请先点选」。"""
    asset_id = mask_asset_id
    if not asset_id:
        if record is None:
            raise EmptySelection
        asset_id = record.get("mask_asset_id")
    if not asset_id:
        raise EmptySelection
    try:
        parsed = uuid.UUID(str(asset_id))
    except ValueError as error:
        raise EmptySelection from error
    asset = await assets_service.get_for_user(session, user_id, parsed)
    if asset is None or asset.kind is not AssetKind.mask:
        raise EmptySelection
    return await get_object(asset.storage_key)


async def describe_fact(session_id: uuid.UUID, revision: int) -> str:
    """Agent 画布摘要的选区事实：Redis 故障降级为无选区（摘要不因旁路故障失败）。"""
    try:
        payload = await get(session_id, revision)
    except redis.exceptions.RedisError:
        return "当前无选区"
    if not payload:
        return "当前无选区"
    markers = payload.get("markers") or []
    if markers:
        return f"已有选区，{len(markers)} 个标点"
    return "已有笔刷选区"


async def _store(
    session_id: uuid.UUID,
    revision: int,
    mask_asset_id: str,
    markers: list[dict[str, Any]],
) -> None:
    payload = json.dumps(
        {"revision": revision, "mask_asset_id": mask_asset_id, "markers": markers},
        ensure_ascii=False,
    )
    await events.redis_client().set(_key(session_id), payload, ex=SELECTION_TTL_SECONDS)


async def _segment_to_overlay(source: bytes, points: list[tuple[float, float]]) -> bytes:
    """点选分割 + 空选区检查：SAM 可能对无人区返回空遮罩——空选区不是选区。"""
    overlay = await asyncio.to_thread(segment.segment_points, source, points)
    image = Image.open(io.BytesIO(overlay)).convert("RGBA")
    if image.getchannel("A").getextrema()[1] == 0:
        raise BlankSelection
    return overlay
