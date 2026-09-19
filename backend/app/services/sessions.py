"""编辑会话服务：建会话、切图、快照式撤销、墙与历史读写；SessionNotFound 由路由翻 404。

apply_edit 是一切可撤销编辑的单一入口：before/after 快照、截断重做分支、
revision 递进、墙附加、seq 分配五件事必须在同一事务同一入口完成——任何绕过
它直接改 document 的路径都会造出不可撤销或不可重做的状态。undo/redo 是快照
恢复不是反向算子（裁剪信息论上不可逆），history_seq 是撤销指针不是 max(seq)。
"""
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy import update as orm_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.layers import LayerDocument, document_of
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


class CannotUndo(Exception):
    """没有可撤销的操作——路由翻 409。"""


class CannotRedo(Exception):
    """没有可重做的操作——路由翻 409。"""


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
    """id + user_id 联合条件；未命中抛 SessionNotFound（404 不泄露存在性）。

    populate_existing 强制以库内最新状态覆盖身份映射里的既有对象：
    同一请求内 execute 失败分支的 rollback 或 Core UPDATE 会把对象置为
    expired，普通 select 不会复活它——后续属性访问在 AsyncSession 下直接
    MissingGreenlet。本函数是所有响应构建的取数入口，必须永远可读。
    """
    row = await session.scalar(
        select(EditSession)
        .where(EditSession.id == session_id, EditSession.user_id == user_id)
        .execution_options(populate_existing=True)
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


def snapshot(row: EditSession) -> dict[str, Any]:
    """可撤销状态的最小全集：document / current_asset_id / revision 三字段。"""
    return {
        "document": row.document,
        "current_asset_id": str(row.current_asset_id),
        "revision": row.revision,
    }


async def apply_edit(
    session: AsyncSession,
    row: EditSession,
    action: str,
    *,
    params: dict[str, Any] | None = None,
    document: LayerDocument | None = None,
    current: Asset | None = None,
    extra_assets: Sequence[uuid.UUID] = (),
    result: dict[str, Any] | None = None,
    bump_revision: bool = True,
) -> None:
    """一切可撤销编辑的单一入口，同事务完成六件事：

    记 before 快照 → 应用变化 → revision 递进 → 附加墙资产 → 截断重做分支
    → 追加历史（params 带 before、result 带 after 快照）并推进 history_seq。
    document 深比较后才算 changed：无变化不算一步编辑（不推进指针、不截断
    重做），防住幂等重放的空历史条目挤掉用户的重做分支。
    """
    before = snapshot(row)
    changed = False

    current_changed = False
    if current is not None and current.id != row.current_asset_id:
        row.current_asset_id = current.id
        if document is None:  # 切换是画布语义级变化：document 缺省整体重建
            row.document = document_of(current).model_dump(mode="json")
        current_changed = True
    if document is not None:
        doc_json = document.model_dump(mode="json")
        if doc_json != row.document:
            row.document = doc_json
            changed = True

    wall_changed = False
    targets = list(dict.fromkeys(extra_assets))
    if current_changed:
        targets.append(current.id)  # 新当前图一并进墙（不挤掉旧图）
    for asset_id in dict.fromkeys(targets):
        if await _add_to_wall(session, row, asset_id):
            wall_changed = True
    changed = changed or current_changed or wall_changed

    if bump_revision and changed:
        row.revision += 1
    if not changed:
        return

    # 新编辑截断重做分支：线性历史的定义——undo 之后一旦有新操作，被撤的未来整体删除
    await session.execute(
        delete(EditHistory).where(
            EditHistory.session_id == row.id, EditHistory.seq > row.history_seq
        )
    )
    await _append_history(
        session,
        row,
        action,
        {**(params or {}), "before": before},
        {**(result or {}), "after": snapshot(row)},
    )
    await session.commit()


async def undo(session: AsyncSession, row: EditSession) -> None:
    """恢复当前条目的 before 快照，指针 −1；seq 1 是建会话，撤到"无"没有意义。"""
    if row.history_seq <= 1:
        raise CannotUndo
    entry = await session.scalar(
        select(EditHistory).where(
            EditHistory.session_id == row.id, EditHistory.seq == row.history_seq
        )
    )
    before = (entry.params or {}).get("before") if entry is not None else None
    # 存量条目（S8/S9 期落库）没有 before 快照：不可撤销，不崩溃不误恢复
    if not before or "document" not in before:
        raise CannotUndo
    updated = await session.execute(
        orm_update(EditSession)
        .where(EditSession.id == row.id, EditSession.history_seq == row.history_seq)
        .values(
            history_seq=row.history_seq - 1,
            document=before["document"],
            current_asset_id=uuid.UUID(before["current_asset_id"]),
            revision=before["revision"],
        )
    )
    if updated.rowcount == 0:  # 并发窗口：指针已被另一请求移动
        await session.rollback()
        raise CannotUndo
    await session.commit()


async def redo(session: AsyncSession, row: EditSession) -> None:
    """重放 seq+1 条目的 after 快照，指针 +1；被截断或没有条目则无可重做。"""
    entry = await session.scalar(
        select(EditHistory).where(
            EditHistory.session_id == row.id, EditHistory.seq == row.history_seq + 1
        )
    )
    after = (entry.result or {}).get("after") if entry is not None else None
    if not after or "document" not in after:
        raise CannotRedo
    updated = await session.execute(
        orm_update(EditSession)
        .where(EditSession.id == row.id, EditSession.history_seq == row.history_seq)
        .values(
            history_seq=row.history_seq + 1,
            document=after["document"],
            current_asset_id=uuid.UUID(after["current_asset_id"]),
            revision=after["revision"],
        )
    )
    if updated.rowcount == 0:
        await session.rollback()
        raise CannotRedo
    await session.commit()


async def undo_state(session: AsyncSession, row: EditSession) -> tuple[bool, bool]:
    """(can_undo, can_redo)：can_undo = 指针 > 1；can_redo = max(seq) > 指针。"""
    max_seq = await session.scalar(
        select(func.max(EditHistory.seq)).where(EditHistory.session_id == row.id)
    )
    return row.history_seq > 1, (max_seq or 0) > row.history_seq


async def previous_document(session: AsyncSession, row: EditSession) -> LayerDocument | None:
    """当前条目 params.before 里的文档——对比模式的"前"侧；无快照（存量条目）为 None。"""
    entry = await session.scalar(
        select(EditHistory).where(
            EditHistory.session_id == row.id, EditHistory.seq == row.history_seq
        )
    )
    before = (entry.params or {}).get("before") if entry is not None else None
    if not before or not before.get("document"):
        return None
    return LayerDocument.model_validate(before["document"])


async def record_result(
    session: AsyncSession,
    row: EditSession,
    *,
    action: str,
    params: dict[str, Any],
    result: dict[str, Any],
    asset_ids: Sequence[uuid.UUID] = (),
) -> None:
    """生成类产出留痕：apply_edit 封装——进墙 + 历史，不切当前图、revision 不变。"""
    await apply_edit(
        session,
        row,
        action,
        params=params,
        extra_assets=asset_ids,
        result=result,
        bump_revision=False,
    )


async def _append_history(
    session: AsyncSession,
    row: EditSession,
    action: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """seq 取 history_seq+1（撤销指针分配，不是 max+1）；(session_id, seq) 唯一约束
    兜底并发，撞约束按库内最新指针顺延重试一次；同事务剪枝防无界增长。"""
    seq = row.history_seq + 1
    for attempt in (1, 2):
        try:
            async with session.begin_nested():
                session.add(
                    EditHistory(
                        user_id=row.user_id,
                        session_id=row.id,
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
            await session.refresh(row)
            seq = row.history_seq + 1
        else:
            break
    row.history_seq = seq
    if seq > HISTORY_LIMIT:
        await session.execute(
            delete(EditHistory).where(
                EditHistory.session_id == row.id, EditHistory.seq <= seq - HISTORY_LIMIT
            )
        )


async def _add_to_wall(session: AsyncSession, row: EditSession, asset_id: uuid.UUID) -> bool:
    """已在墙内则不重复；position 取 max+1 显式递增。返回是否真的新增。"""
    existing = await session.scalar(
        select(SessionAsset).where(
            SessionAsset.session_id == row.id, SessionAsset.asset_id == asset_id
        )
    )
    if existing is not None:
        return False
    max_pos = await session.scalar(
        select(func.max(SessionAsset.position)).where(SessionAsset.session_id == row.id)
    )
    session.add(SessionAsset(session_id=row.id, asset_id=asset_id, position=(max_pos or 0) + 1))
    return True


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    current_asset_id: uuid.UUID,
    asset_ids: list[uuid.UUID],
    title: str | None,
) -> EditSession:
    """建会话：history_seq=0 落行，首条历史（create_session）把指针推进到 1。

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
        history_seq=0,
        document=document_of(current).model_dump(mode="json"),
    )
    session.add(row)
    await session.flush()

    session.add(SessionAsset(session_id=row.id, asset_id=current.id, position=1))
    for offset, asset_id in enumerate(others, start=2):
        session.add(SessionAsset(session_id=row.id, asset_id=asset_id, position=offset))

    await _append_history(
        session, row, "create_session", {}, {"asset_id": str(current.id)}
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
    切图改写为 apply_edit 封装：快照入库，从此可撤销。
    """
    row = await get_for_user(session, user_id, session_id)
    new_title = changes.get("title")
    new_asset_id = changes.get("current_asset_id")
    if isinstance(new_title, str):
        row.title = normalize_title(new_title)
    if isinstance(new_asset_id, uuid.UUID) and new_asset_id != row.current_asset_id:
        asset = await _require_asset(session, user_id, new_asset_id)
        await apply_edit(
            session, row, "switch_current", current=asset, params={"asset_id": str(asset.id)}
        )
    await session.commit()
    return row
