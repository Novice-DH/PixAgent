"""编辑会话服务：建会话、切图、墙与历史读写；SessionNotFound 由路由翻 404。

切图由服务端同事务整体重建 document——current、document、墙、历史、revision
五处一致只能在同一个事务里落定，前端不得本地拼文档。会话接口全程纯同步
CRUD 事务，不碰 Redis 与队列：Redis 停机不影响会话可用性。
"""
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.layers import document_of
from app.models.asset import Asset
from app.models.edit_history import HISTORY_LIMIT, EditHistory
from app.models.edit_session import EditSession, SessionAsset

DEFAULT_TITLE = "未命名会话"
TITLE_MAX_LENGTH = 80
MAX_WALL_ASSETS = 12
SESSION_NOT_FOUND = "会话不存在"
ASSET_NOT_FOUND = "素材不存在"


class SessionNotFound(Exception):
    """会话不存在或不属于该用户——路由翻 404，不泄露存在性。"""


class AssetNotFound(Exception):
    """资产不存在或不属于该用户——路由翻 404，同一文案不区分两种情形。"""


def normalize_title(title: str | None) -> str:
    """标题归一单点：全部空白折叠、截断 80 字、清洗后为空落「未命名会话」。"""
    cleaned = " ".join((title or "").split())
    if not cleaned:
        return DEFAULT_TITLE
    return cleaned[:TITLE_MAX_LENGTH]


async def _require_asset(session: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    asset = await session.scalar(
        select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id)
    )
    if asset is None:
        raise AssetNotFound
    return asset


async def get_for_user(
    session: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> EditSession:
    """id + user_id 联合条件；未命中抛 SessionNotFound（404 不泄露存在性）。"""
    row = await session.scalar(
        select(EditSession).where(EditSession.id == session_id, EditSession.user_id == user_id)
    )
    if row is None:
        raise SessionNotFound
    return row


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, limit: int
) -> list[EditSession]:
    result = await session.execute(
        select(EditSession)
        .where(EditSession.user_id == user_id)
        .order_by(EditSession.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def wall_assets(
    session: AsyncSession, session_id: uuid.UUID
) -> list[tuple[int, Asset]]:
    """图片墙按显式 position 升序；同事务插入的多行时间戳相同，顺序只认 position。"""
    result = await session.execute(
        select(SessionAsset, Asset)
        .join(Asset, Asset.id == SessionAsset.asset_id)
        .where(SessionAsset.session_id == session_id)
        .order_by(SessionAsset.position.asc())
    )
    return [(row.position, asset) for row, asset in result.all()]


async def history_of(
    session: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> list[EditHistory]:
    await get_for_user(session, user_id, session_id)
    result = await session.execute(
        select(EditHistory)
        .where(EditHistory.session_id == session_id)
        .order_by(EditHistory.seq.desc())
    )
    return list(result.scalars())


async def load(session: AsyncSession, session_id: uuid.UUID) -> EditSession:
    """Worker 侧按 id 加载：任务已持有归属上下文，无需 user 条件（对齐 runs.load）。"""
    row = await session.scalar(select(EditSession).where(EditSession.id == session_id))
    if row is None:
        raise SessionNotFound
    return row


async def record_result(
    session: AsyncSession,
    row: EditSession,
    *,
    action: str,
    params: dict[str, Any],
    result: dict[str, Any],
    asset_ids: Sequence[uuid.UUID] = (),
) -> None:
    """会话内工具产出留痕单点：并入图片墙 + 追加编辑记录，同一个事务落定。

    不切当前图——current_asset_id / document / revision 均不动：工具说"改好了"
    就换图等于夺走用户的否决权，采用动作永远是显式的（点图片墙）。
    """
    for asset_id in asset_ids:
        await _add_to_wall(session, row, asset_id)
    await _append_history(session, row.user_id, row.id, action, params, result)
    await session.commit()


async def _append_history(
    session: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    action: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """seq 取 max+1，(session_id, seq) 唯一约束兜底并发；同事务剪枝防无界增长。

    剪枝条件按"追加后的 max"计算：保留最近 HISTORY_LIMIT 条，删 seq <= max - 20。
    """
    # seq 取 max+1；并发窗口下撞 (session_id, seq) 唯一约束时在保存点内重试一次——
    # 数据库唯一约束是最后一道闸，重试之外不做更复杂的序号分配
    seq = 0
    for attempt in (1, 2):
        max_seq = await session.scalar(
            select(func.max(EditHistory.seq)).where(EditHistory.session_id == session_id)
        )
        seq = (max_seq or 0) + 1
        try:
            async with session.begin_nested():
                session.add(
                    EditHistory(
                        user_id=user_id,
                        session_id=session_id,
                        seq=seq,
                        action=action,
                        params=params,
                        result=result,
                    )
                )
                await session.flush()
        except IntegrityError:
            if attempt == 2:
                raise
        else:
            break
    if seq > HISTORY_LIMIT:
        await session.execute(
            delete(EditHistory).where(
                EditHistory.session_id == session_id, EditHistory.seq <= seq - HISTORY_LIMIT
            )
        )


async def _add_to_wall(session: AsyncSession, row: EditSession, asset_id: uuid.UUID) -> None:
    """已在墙内则不重复；position 取 max+1 显式递增。"""
    existing = await session.scalar(
        select(SessionAsset).where(
            SessionAsset.session_id == row.id, SessionAsset.asset_id == asset_id
        )
    )
    if existing is not None:
        return
    max_pos = await session.scalar(
        select(func.max(SessionAsset.position)).where(SessionAsset.session_id == row.id)
    )
    session.add(SessionAsset(session_id=row.id, asset_id=asset_id, position=(max_pos or 0) + 1))


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    current_asset_id: uuid.UUID,
    asset_ids: list[uuid.UUID],
    title: str | None,
) -> EditSession:
    """建会话：document=document_of(current)、revision=1、墙初始化、create_session 历史。

    未采用的候选一并进墙（保序去重、忽略 current 本身），随时切回而不是丢弃。
    """
    current = await _require_asset(session, user_id, current_asset_id)
    # 全部候选先批量校验归属，再开始写入：未知 id 在任何落库前就 404
    others = [aid for aid in dict.fromkeys(asset_ids) if aid != current.id]
    if others:
        result = await session.execute(
            select(Asset.id).where(Asset.id.in_(others), Asset.user_id == user_id)
        )
        if len(set(result.scalars())) != len(others):
            raise AssetNotFound

    row = EditSession(
        user_id=user_id,
        title=normalize_title(title),
        original_asset_id=current.id,
        current_asset_id=current.id,
        revision=1,
        document=document_of(current).model_dump(mode="json"),
    )
    session.add(row)
    await session.flush()

    session.add(SessionAsset(session_id=row.id, asset_id=current.id, position=1))
    for offset, asset_id in enumerate(others, start=2):
        session.add(SessionAsset(session_id=row.id, asset_id=asset_id, position=offset))

    await _append_history(
        session, user_id, row.id, "create_session", {}, {"asset_id": str(current.id)}
    )
    await session.commit()
    return row


async def update(
    session: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    changes: dict[str, Any],
) -> EditSession:
    """改会话：只认 title / current_asset_id；changes 由路由 exclude_unset 而来。

    未提供（含空对象）零变化——SQLAlchemy 对未变更属性不产生 UPDATE，
    updated_at 的 onupdate 也不会触发。显式 null 视为未提供（会话必须有当前图）。
    """
    row = await get_for_user(session, user_id, session_id)
    new_title = changes.get("title")
    new_asset_id = changes.get("current_asset_id")
    if isinstance(new_title, str):
        row.title = normalize_title(new_title)
    if isinstance(new_asset_id, uuid.UUID):
        if new_asset_id != row.current_asset_id:
            asset = await _require_asset(session, user_id, new_asset_id)
            # 切换是画布语义级变化（画幅都变了）：五处状态同事务整体落定
            row.current_asset_id = asset.id
            row.document = document_of(asset).model_dump(mode="json")
            row.revision += 1
            await _add_to_wall(session, row, asset.id)
            await _append_history(
                session, row.user_id, row.id,
                "switch_current",
                {"asset_id": str(asset.id)},
                {"revision": row.revision},
            )
        # 切回同一张：完全 no-op，不产生任何变化
    await session.commit()
    return row
