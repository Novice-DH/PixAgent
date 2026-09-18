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
from app.services import runs
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


async def submit(
    session: AsyncSession, user_id: uuid.UUID, tool: str, params: dict[str, Any]
) -> ToolRun:
    """受理：服务端校验 → 落 run → 投递统一任务；job id = run id 幂等。"""
    validate(tool, params)
    run = await runs.create(session, user_id, tool, params)
    await queue.enqueue(TOOL_TASK, run.id)
    return run


async def execute(session: AsyncSession, run: ToolRun) -> None:
    """统一外壳：start → handler → finish；状态机与兜底收口在这一处。"""
    # rollback 会过期 ORM 实例：失败路径重载只认提前取好的主键，
    # 同步访问过期属性会触发隐式刷新，在 AsyncSession 下抛 MissingGreenlet
    run_id = run.id
    tool = run.tool
    try:
        await runs.start(session, run)
        result = await spec_of(tool).handler(session, run)
        await runs.finish_succeeded(session, run, result)
    except (ProviderError, UnknownTool) as error:
        await runs.finish_failed(session, run, str(error))
    except Exception:
        # 未预期异常：细节只进日志，对外统一话术——堆栈不该出现在 UI
        logger.exception("工具执行未预期失败 run=%s tool=%s", run_id, tool)
        await session.rollback()
        fresh = await runs.load(session, run_id)
        if fresh is not None and not fresh.status.is_terminal:
            await runs.finish_failed(session, fresh, EXECUTION_FAILURE_MESSAGE)
