"""健康检查路由：可观测性设施，依赖故障时“报告”而不是放大为 500。"""
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db import SessionDep

router = APIRouter(prefix="/health")


async def _probe(session: Any) -> str:
    """执行一次数据库探测；任何异常都折叠为 `error: <异常类名>`，HTTP 仍 200。"""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        return f"error: {type(exc).__name__}"
    return "ok"


@router.get("")
async def health(session: SessionDep) -> dict[str, str]:
    return {"api": "ok", "database": await _probe(session)}
