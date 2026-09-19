"""统一工具执行通道：注册表校验、受理投递、状态机外壳——所有工具共用。

submit 是 API 侧唯一受理入口，execute 是 Worker 侧唯一状态机入口：
具体工具的 handler 只做业务、只返回结果字典，不碰状态机——状态机写进
具体工具，第二个工具就会抄错第一个的兜底。
"""
import logging
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app import queue
from app.layers import LayerDocument
from app.models.tool_run import ToolRun
from app.providers import ProviderError
from app.services import assets, runs, sessions
from app.tools import UnknownTool, spec_of
from app.tools.context import ToolError

logger = logging.getLogger(__name__)

TOOL_TASK = "run_tool"
EXECUTION_FAILURE_MESSAGE = "执行失败，请重试"
SESSION_REQUIRED_MESSAGE = "此工具需要在编辑会话中使用"


class InvalidParams(Exception):
    """工具参数未通过注册表模型校验——路由翻 422，规划链翻「执行不了」话术。"""


def validate(tool: str, params: dict[str, Any]) -> None:
    """模型给出的计划一律经服务端校验，绝不直接执行；非法参数在这里被挡下。"""
    try:
        spec_of(tool).params.model_validate(params)
    except ValidationError as error:
        raise InvalidParams(_first_error(error)) from None


def _first_error(error: ValidationError) -> str:
    """首条错误格式「字段路径：原因」；loc 为空时字段名为「参数」。"""
    first = error.errors()[0]
    path = ".".join(str(part) for part in first["loc"]) or "参数"
    return f"{path}：{first['msg']}"


def _normalize(tool: str, params: dict[str, Any]) -> dict[str, Any]:
    """落库前按注册表模型归一：默认值补齐、JSON 安全——handler 读到的 params
    与创作页受理路径（to_params）完全一致，模型省略可选参数时不会 KeyError。"""
    model = spec_of(tool).params.model_validate(params)
    return model.model_dump(mode="json", exclude_none=True)


async def submit(
    session: AsyncSession,
    user_id: uuid.UUID,
    tool: str,
    params: dict[str, Any],
    session_id: uuid.UUID | None = None,
) -> ToolRun:
    """受理：服务端校验 → 落 run → 按工具的执行通道分叉。

    queued=False（文档工具）：毫秒级纯计算不进队列——同步 execute 后 refresh，
    202 响应一次带回终态 run 与新会话，前端零轮询；queued=True（像素/生成）：
    投递统一任务，job id = run id 幂等。session_required 的工具缺会话上下文
    直接 InvalidParams——受理期就挡下，不浪费一次落库。
    """
    spec = spec_of(tool)
    if spec.session_required and session_id is None:
        raise InvalidParams(SESSION_REQUIRED_MESSAGE)
    validate(tool, params)
    run = await runs.create(
        session, user_id, tool, _normalize(tool, params), session_id=session_id
    )
    if not spec.queued:
        await execute(session, run)
        await session.refresh(run)
        return run
    await queue.enqueue(TOOL_TASK, run.id)
    return run


async def execute(session: AsyncSession, run: ToolRun) -> None:
    """统一外壳：start → handler → 会话留痕 → finish；状态机与兜底收口在这一处。"""
    # rollback 会过期 ORM 实例：失败路径重载只认提前取好的主键，
    # 同步访问过期属性会触发隐式刷新，在 AsyncSession 下抛 MissingGreenlet
    run_id = run.id
    tool = run.tool
    try:
        await runs.start(session, run)
        result = await spec_of(tool).handler(session, run)
        await _record(session, run, result)
        await runs.finish_succeeded(session, run, result)
    except (ProviderError, UnknownTool, ToolError) as error:
        # 与未预期分支同款先回滚再落终态：外壳是全工具共用的，不能假设 handler
        # 抛明确异常时没留脏状态——rollback 后按主键重载，错误信息保留原文
        await session.rollback()
        fresh = await runs.load(session, run_id)
        if fresh is not None and not fresh.status.is_terminal:
            await runs.finish_failed(session, fresh, str(error))
    except Exception:
        # 未预期异常：细节只进日志，对外统一话术——堆栈不该出现在 UI
        logger.exception("工具执行未预期失败 run=%s tool=%s", run_id, tool)
        await session.rollback()
        fresh = await runs.load(session, run_id)
        if fresh is not None and not fresh.status.is_terminal:
            await runs.finish_failed(session, fresh, EXECUTION_FAILURE_MESSAGE)


async def _record(session: AsyncSession, run: ToolRun, result: dict[str, Any] | None) -> None:
    """产出采用策略分层：result 的形态决定走哪条 apply_edit 通道。

    含 document（文档工具）→ 文档变化入库；含 adopt_asset_id（像素工具）→
    产出直接采用为当前图；仅 asset_ids（生成类）→ 只进墙不切当前图、revision
    不变。run 无会话（创作页直发）不留痕；会话已删静默返回——异步执行时用户
    可能已经删掉会话，产出无处安放也不该让执行失败。
    """
    if run.session_id is None:
        return
    try:
        row = await sessions.load(session, run.session_id)
    except sessions.SessionNotFound:
        return
    result = result or {}
    asset_ids = [
        asset.id
        for raw_id in result.get("asset_ids") or []
        if (asset := await assets.get_for_user(session, run.user_id, uuid.UUID(str(raw_id))))
        is not None
    ]
    if result.get("document") is not None:
        await sessions.apply_edit(
            session,
            row,
            run.tool,
            params=run.params,
            document=LayerDocument.model_validate(result["document"]),
            extra_assets=asset_ids,
            result=_history_result(result),
        )
        return
    adopt_raw = result.get("adopt_asset_id")
    if adopt_raw:
        adopt = await assets.get_for_user(session, run.user_id, uuid.UUID(str(adopt_raw)))
        if adopt is not None:
            await sessions.apply_edit(
                session,
                row,
                run.tool,
                params=run.params,
                current=adopt,
                extra_assets=[*asset_ids, adopt.id],
                result=_history_result(result),
            )
            return
    await sessions.record_result(
        session, row, action=run.tool, params=run.params, result=result, asset_ids=asset_ids
    )


def _history_result(result: dict[str, Any]) -> dict[str, Any]:
    """历史 result 不重复存整份新文档——after 快照已含 document，防 JSONB 翻倍。"""
    return {key: value for key, value in result.items() if key != "document"}
