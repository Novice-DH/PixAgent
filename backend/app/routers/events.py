"""SSE 进度流：/events/runs/{run_id}——不挂 /api 前缀，留出反代按路径单独关缓冲的余地。

时序铁律：先订阅 Pub/Sub，再读快照——顺序反了会漏掉两步之间发生的终态。
快照里已有的直接播，订阅后发生的从通道来；终态帧后关闭；已终态任务重放
一帧快照即关闭（页面刷新的恢复路径）。断开无害：客户端重连先收快照。
"""
import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app import events
from app.db import SessionDep
from app.deps import CurrentUser
from app.models.tool_run import RunStatus
from app.services import runs

router = APIRouter(tags=["events"])

# 单连接上限：防僵尸连接堆积；心跳防代理掐闲连接——双保险，断开无害
MAX_CONNECTION_SECONDS = 600.0


def _frame(snapshot: dict) -> str:
    return f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"


_TERMINAL = {RunStatus.succeeded, RunStatus.failed, RunStatus.canceled}


async def _stream(run) -> AsyncIterator[str]:
    subscription = events.RunSubscription(run.id)
    await subscription.subscribe()  # 先订阅——读快照前必须完成
    try:
        current = runs.snapshot(run)
        yield _frame(current)
        if run.status.is_terminal:
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + MAX_CONNECTION_SECONDS
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            snapshot = await subscription.next_snapshot(
                timeout=min(events.IDLE_HEARTBEAT_SECONDS, remaining)
            )
            if snapshot is None:
                yield ": ping\n\n"  # 空闲心跳注释帧
                continue
            yield _frame(snapshot)
            if snapshot["status"] in {s.value for s in _TERMINAL}:
                return
    finally:
        await subscription.aclose()


@router.get("/runs/{run_id}")
async def stream_run(
    run_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> StreamingResponse:
    # 归属检查与普通端点同一套：流式端点不是鉴权旁路
    run = await runs.get_for_user(session, user.id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return StreamingResponse(
        _stream(run),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
