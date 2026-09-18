"""runs 服务：ToolRun 状态机单一入口（create / get / load / start / report / finish）。

progress 取 max(现有, 新值) 保证单调——乱序回调与并发写入不能回拨进度条，
单调性由服务端收口，不信客户端；每次状态落库后立即发布 Redis Pub/Sub，
订阅进度的客户端无缝衔接（先订阅后读快照的时序由 SSE 端点保证）。
"""
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.models.tool_run import RunStatus, ToolRun

logger = logging.getLogger(__name__)


class RunNotFound(Exception):
    """任务不存在或不属于该用户——路由翻 404，不泄露存在性。"""


def _now() -> datetime:
    return datetime.now(UTC)


def snapshot(run: ToolRun) -> dict[str, Any]:
    """进度事件负载：SSE 帧 payload 与 Pub/Sub 消息同一形态。"""
    return {
        "id": str(run.id),
        "tool": run.tool,
        "status": run.status.value,
        "progress": run.progress,
        "stage": run.stage,
        "error": run.error,
    }


async def _publish(run: ToolRun) -> None:
    await events.publish_snapshot(run.id, snapshot(run))


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    tool: str,
    params: dict[str, Any],
    session_id: uuid.UUID | None = None,
) -> ToolRun:
    run = ToolRun(
        user_id=user_id,
        tool=tool,
        # 会话内工具调用才有值；创作页直发为 None，产出不进任何图片墙
        session_id=session_id,
        status=RunStatus.queued,
        progress=0,
        stage="等待开始",
        params=params,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await _publish(run)
    return run


async def get_for_user(
    session: AsyncSession, user_id: uuid.UUID, run_id: uuid.UUID
) -> ToolRun | None:
    """id + user_id 联合条件单一入口：未命中 None，路由翻 404。"""
    result = await session.execute(
        select(ToolRun).where(ToolRun.id == run_id, ToolRun.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def load(session: AsyncSession, run_id: uuid.UUID) -> ToolRun | None:
    """Worker 侧按 id 加载：任务已持有归属上下文，无需 user 条件。"""
    result = await session.execute(select(ToolRun).where(ToolRun.id == run_id))
    return result.scalar_one_or_none()


async def start(session: AsyncSession, run: ToolRun) -> None:
    run.status = RunStatus.running
    run.progress = max(run.progress, 5)
    run.stage = "已开始"
    run.started_at = _now()
    await session.commit()
    await _publish(run)


async def report(session: AsyncSession, run: ToolRun, progress: int, stage: str) -> None:
    if progress <= run.progress and stage == run.stage:
        return
    run.progress = max(run.progress, progress)  # 只增不减
    run.stage = stage
    await session.commit()
    await _publish(run)


async def finish_succeeded(
    session: AsyncSession, run: ToolRun, result: dict[str, Any]
) -> None:
    run.status = RunStatus.succeeded
    run.progress = max(run.progress, 100)
    run.stage = "已完成"
    run.result = result
    run.error = None
    run.finished_at = _now()
    await session.commit()
    await _publish(run)


async def finish_failed(session: AsyncSession, run: ToolRun, error: str) -> None:
    run.status = RunStatus.failed
    run.stage = "已结束"
    run.error = error
    run.finished_at = _now()
    await session.commit()
    await _publish(run)
