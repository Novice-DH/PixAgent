"""ToolSpec 定义：注册表条目的冻结契约。

注册表是三界契约的单一来源——服务端参数校验、Agent 工具描述、（未来的）前端
工具面板都从同一份 ToolSpec 生成；任何"再写一份参数定义"都是漂移的开始。
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_run import ToolRun


class UnknownTool(Exception):
    """注册表中不存在的工具名——verify 节点把它翻成「执行不了」话术，不泄露更多细节。"""


@dataclass(frozen=True)
class ToolSpec:
    """一个工具在注册表里的全部登记信息。

    params 一模两用：服务端校验与模型函数签名同一份——两份定义必漂移，
    漂移的那天就是"界面收的参数 Agent 拒收"。handler 只做业务、返回结果
    字典，不碰状态机（状态机上收 services/tools 的统一外壳）。
    """

    name: str
    label: str
    description: str
    params: type[BaseModel]
    handler: Callable[[AsyncSession, ToolRun], Awaitable[dict[str, Any]]]
    needs_approval: bool = False  # 预留 HITL 开关：本期定义不消费，不许提前实现确认流程
    agent_hidden: tuple[str, ...] = ()  # 不暴露给模型的参数名（服务端上下文决定，模型不该编）
