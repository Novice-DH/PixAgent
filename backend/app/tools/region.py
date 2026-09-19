"""局部消除与局部替换：模型改全图、客户端只合成选区内。

编辑端点没有（可靠的）mask 输入，「全图重绘 + apply_masked 合成」把「局部」
变成纯客户端概念：模型只管改得对，边界由我们画——选区外像素逐字节来自原图，
模型在选区外的任何漂移都被丢弃（提示词约束是软引导，合成是硬边界）。选区是
一次性耗材：工具成功即清，比「记得检查有效期」可靠。
"""
import asyncio
import logging

import redis.exceptions
from pydantic import BaseModel, Field

from app.edits import mask as mask_edits
from app.models.asset import AssetKind, AssetSource
from app.providers import EditRequest, get_image_provider
from app.services import assets as assets_service
from app.services import runs, selections
from app.tools.base import ToolSpec
from app.tools.context import ToolError, flatten_session, require_session

logger = logging.getLogger(__name__)

# 消除语义自足（移除+补背景），默认模板就是完整指令；替换必须知道「换成什么」
_ERASE_PROMPT = "移除选中物体，用周围背景自然填补，不要改变选区以外的画面。"
_REPLACE_TEMPLATE = "只改选中区域：{prompt}。选区外的主体、光线和背景必须保持原样。"


class EraseRegionIn(BaseModel):
    """局部消除：prompt 可空——空则用缺省消除模板。"""

    prompt: str = Field(default="", max_length=500)
    mask_asset_id: str | None = None
    revision: int | None = None


class ReplaceRegionIn(BaseModel):
    """局部替换：prompt 必填——「换成什么」是替换语义的本体。"""

    prompt: str = Field(min_length=1, max_length=500)
    mask_asset_id: str | None = None
    revision: int | None = None


def _progress(session, run):
    """Provider 进度回调直通 runs.report——单调性由服务端收口（取 max 兜底）。"""

    async def on_progress(progress: int, stage: str) -> None:
        await runs.report(session, run, progress, stage)

    return on_progress


async def _edit_region(
    session, run, *, revision: int | None, mask_asset_id: str | None, prompt: str
) -> dict:
    """公共骨架：revision 校验 → 取遮罩 → 全图编辑 → 保内换外合成 → 采用 +
    清选区（一次性消费）。"""
    row = await require_session(session, run)
    # 异步执行期间画布可能已变（点选和工具调用之间可以隔着一次撤销）：
    # 受理时的 409 挡不到这里，执行时再校验一次
    if revision is not None and revision != row.revision:
        raise ToolError(selections.STALE_SELECTION_MESSAGE)
    try:
        record = None
        if mask_asset_id is None:
            record = await selections.get(row.id, row.revision)
        mask = await selections.mask_bytes(session, row.user_id, record, mask_asset_id)
    except (selections.EmptySelection, redis.exceptions.RedisError):
        # 选区缺失与存储不可达都按「没有选区」收口——故障有界（不 500 不崩进程）
        raise ToolError(selections.NO_SELECTION_MESSAGE) from None
    await runs.report(session, run, 20, "读取选区")
    source = await flatten_session(session, row)
    await runs.report(session, run, 40, "局部生成")
    images = await get_image_provider().edit(
        EditRequest(prompt=prompt, image=source),
        _progress(session, run),
    )
    if not images:
        raise ToolError("模型没有返回编辑结果")
    await runs.report(session, run, 85, "合并选区")
    merged = await asyncio.to_thread(mask_edits.apply_masked, source, images[0], mask)
    asset = await assets_service.create_from_bytes(
        session, run.user_id, merged, kind=AssetKind.generated, source=AssetSource.tool
    )
    try:
        await selections.clear(row.id)
    except redis.exceptions.RedisError:
        # 清理失败不回滚已完成的编辑：24h TTL 与 revision 双兜底，日志留痕即可
        logger.warning("选区清理失败 run=%s session=%s", run.id, row.id)
    return {"asset_ids": [str(asset.id)], "adopt_asset_id": str(asset.id)}


async def erase_region(session, run) -> dict:
    params = EraseRegionIn.model_validate(run.params)
    prompt = params.prompt.strip() or _ERASE_PROMPT
    return await _edit_region(
        session, run, revision=params.revision, mask_asset_id=params.mask_asset_id, prompt=prompt
    )


async def replace_region(session, run) -> dict:
    params = ReplaceRegionIn.model_validate(run.params)
    prompt = _REPLACE_TEMPLATE.format(prompt=params.prompt.strip())
    return await _edit_region(
        session, run, revision=params.revision, mask_asset_id=params.mask_asset_id, prompt=prompt
    )


ERASE_REGION = ToolSpec(
    name="erase_region",
    label="局部消除",
    description="移除选中的物体或区域，用周围背景自然填补，选区以外的画面保持不变",
    params=EraseRegionIn,
    handler=erase_region,
    agent_hidden=("mask_asset_id", "revision"),
    session_required=True,
)
REPLACE_REGION = ToolSpec(
    name="replace_region",
    label="局部替换",
    description="按文字描述只修改选中的区域，选区外的主体、光线和背景保持原样",
    params=ReplaceRegionIn,
    handler=replace_region,
    agent_hidden=("mask_asset_id", "revision"),
    session_required=True,
)
