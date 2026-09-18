"""规划模型接入：OpenAI 兼容模式 + 工具签名从注册表生成。

文本规划模型走 compatible-mode、图像生成走原生异步接口——同一平台的
两条接入路径，不合并（合并配置只会两头别扭）。temperature=0：规划要
确定性，同一句话同一计划，测试与回放才可能。
"""
from functools import lru_cache
from typing import Any

from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.tools import SPECS

PLANNER_UNAVAILABLE_MESSAGE = "未配置 DASHSCOPE_API_KEY，对话指令不可用"


class PlannerUnavailable(Exception):
    """规划模型不可用（未配置 DASHSCOPE_API_KEY）——respond 落 failed 轮并把原文透出。"""


def _tool_schemas() -> list[dict[str, Any]]:
    """从注册表生成全部函数签名：name/description 用 spec 的（覆盖参数模型默认值）。

    agent_hidden 的参数从 properties 与 required 双处剥除——漏一处，模型就会
    调用一个不存在的必填参数；seed 与素材 ID 由服务端上下文决定，模型不该编。
    """
    schemas: list[dict[str, Any]] = []
    for spec in SPECS:
        schema = convert_to_openai_function(spec.params)
        parameters = schema.get("parameters", {})
        parameters["properties"] = {
            name: prop
            for name, prop in parameters.get("properties", {}).items()
            if name not in spec.agent_hidden
        }
        parameters["required"] = [
            name for name in parameters.get("required", []) if name not in spec.agent_hidden
        ]
        schema["name"] = spec.name
        schema["description"] = spec.description
        schemas.append(schema)
    return schemas


@lru_cache
def planner() -> ChatOpenAI:
    """绑定全部注册表签名的规划模型；进程内一次构建（工具签名在绑定时固化）。

    未配 key 抛 PlannerUnavailable（异常不被 lru_cache 缓存，配置补上后
    下一次调用即可用）；改了 SPECS 或配置的测试必须 planner.cache_clear()。
    """
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise PlannerUnavailable(PLANNER_UNAVAILABLE_MESSAGE)
    return ChatOpenAI(
        model=settings.planner_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url + "/compatible-mode/v1",
        temperature=0,
    ).bind_tools(_tool_schemas())
