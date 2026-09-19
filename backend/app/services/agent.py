"""Agent 服务：一轮对话的规则与事务；不 import fastapi。

respond 无论成败都落一条 AgentRun——规划失败也落库（failed + error）：
对话是用户的心智模型，说了话就该有回音，沉默失败迫使用户反复重发探测。
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import graph
from app.agent.llm import PlannerUnavailable
from app.models.agent_run import AgentRun
from app.models.asset import Asset
from app.models.edit_session import EditSession
from app.models.tool_run import RunStatus
from app.services import selections

logger = logging.getLogger(__name__)

PLANNING_FAILURE_MESSAGE = "规划失败，请重试"


async def _describe(session: AsyncSession, record: EditSession) -> str:
    """画布摘要：只给规划决策必需的元数据事实，不含图片内容理解；选区事实让
    「把骨头换成黑色」这类一句话直达局部工具，不再反问重选。"""
    document = record.document or {}
    layers = document.get("layers") or []
    asset = await session.get(Asset, record.current_asset_id)
    fmt = asset.image_format if asset is not None else "未知"
    alpha = "（含透明通道）" if asset is not None and asset.has_alpha else ""
    fact = await selections.describe_fact(record.id, record.revision)
    return (
        f"画幅 {document.get('width')}×{document.get('height')}，"
        f"图层 {len(layers)} 个，修订号 {record.revision}，当前图 {fmt}{alpha}，{fact}"
    )


async def respond(session: AsyncSession, record: EditSession, goal: str) -> AgentRun:
    """处理一轮对话：画布摘要 → 规划链 → 落 AgentRun，提交后 refresh 返回。"""
    # 先取好主键与修订号：rollback 会过期 ORM 实例，失败路径不再碰 record
    user_id = record.user_id
    session_id = record.id
    revision = record.revision
    context = await _describe(session, record)
    turn = AgentRun(
        user_id=user_id,
        session_id=session_id,
        revision=revision,
        goal=goal,
        status=RunStatus.failed,
    )
    try:
        reply, plan = await graph.run(
            goal, context, graph.AgentDeps(session=session, user_id=user_id, session_id=session_id)
        )
    except PlannerUnavailable as error:
        turn.error = str(error)
    except Exception:
        # 环境故障与未预期异常都落 failed 轮——不抛 503，用户的话不能丢
        await session.rollback()
        logger.exception("规划链未预期失败 session=%s", session_id)
        turn.error = PLANNING_FAILURE_MESSAGE
    else:
        turn.status = RunStatus.succeeded
        turn.reply = reply
        turn.plan = plan
    session.add(turn)
    await session.commit()
    await session.refresh(turn)
    return turn


async def turns_of(
    session: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> list[AgentRun]:
    """对话按 created_at 正序，limit 50。"""
    result = await session.execute(
        select(AgentRun)
        .where(AgentRun.session_id == session_id, AgentRun.user_id == user_id)
        .order_by(AgentRun.created_at.asc())
        .limit(50)
    )
    return list(result.scalars())
