"""健康检查路由：可观测性设施，依赖故障时"报告"而不是放大为 500。

健康契约随依赖清单演进：本期加入 storage——database 与 storage 并发探测
（asyncio.gather），未来加依赖照抄此模式。
"""
import asyncio
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db import SessionDep
from app.storage import check as check_storage

router = APIRouter(prefix="/health")


async def _fold_probe(coro) -> str:
    """执行一次探测；任何异常都折叠为 `error: <异常类名>`，HTTP 仍 200。"""
    try:
        await coro
    except Exception as exc:
        return f"error: {type(exc).__name__}"
    return "ok"


async def _probe_database(session: Any) -> None:
    await session.execute(text("SELECT 1"))


@router.get("")
async def health(session: SessionDep) -> dict[str, str]:
    database_state, storage_state = await asyncio.gather(
        _fold_probe(_probe_database(session)),
        _fold_probe(check_storage()),
    )
    return {"api": "ok", "database": database_state, "storage": storage_state}
