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
from app.models.tool_run import ToolRun
from app.providers import ProviderError
from app.services import assets, runs, sessions
from app.tools import UnknownTool, spec_of

logger = logging.getLogger(__name__)

TOOL_TASK = "run_tool"
EXECUTION_FAILURE_MESSAGE = "执行失败，请重试"


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
    """受理：服务端校验 → 落 run → 投递统一任务；job id = run id 幂等。

    会话内调用传 session_id（产出经 _record 进图片墙）；创作页直发不传。
    """
    validate(tool, params)
    run = await runs.create(
        session, user_id, tool, _normalize(tool, params), session_id=session_id
    )
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
    except (ProviderError, UnknownTool) as error:
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


async def _record(session: AsyncSession, run: ToolRun, result: dict[str, Any]) -> None:
    """会话留痕：工具产出并入图片墙 + 写编辑记录（action=tool 名）——不改当前图。

    run 无会话（创作页直发）不留痕；会话已删静默返回——异步执行时用户
    可能已经删掉会话，产出无处安放也不该让执行失败。
    """
    if run.session_id is None:
        return
    try:
        row = await sessions.load(session, run.session_id)
    except sessions.SessionNotFound:
        return
    asset_ids = [
        asset.id
        for raw_id in (result or {}).get("asset_ids") or []
        if (asset := await assets.get_for_user(session, run.user_id, uuid.UUID(str(raw_id))))
        is not None
    ]
    await sessions.record_result(
        session, row, action=run.tool, params=run.params, result=result, asset_ids=asset_ids
    )
