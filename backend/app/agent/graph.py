"""规划链：plan → verify → dispatch 三节点两段图（LangGraph）。

模型给出的计划一律经服务端校验，绝不直接执行——verify 是安全边界不是
流程装饰：LLM 会幻觉出未注册的工具名、编造越界参数，全部挡在这里。
状态 TypedDict 可序列化；AgentDeps 经 config.configurable 注入，不进
state——数据库会话不是可序列化对象，这也是 checkpoint 持久化的前置条件。
"""
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import planner
from app.services import tools
from app.tools import UnknownTool, label_of, spec_of

FALLBACK_REPLY = "没太理解这条指令，换个说法或说得更具体一些。"

SYSTEM_PROMPT = """你是图片编辑器里的修图助手。规则：
1. 只能使用已提供的工具，每轮最多安排一步。
2. 缺少的参数用当前画布信息与常识补齐，可以推断就不要反问用户。
3. 与修图无关、或者你做不到的请求，用一句中文说明，不要调用工具。
4. 画布摘要标明已有选区时，局部消除/替换可直接调用，不要再让用户重选。
当前画布："""


@dataclass(frozen=True)
class AgentDeps:
    """执行依赖：数据库会话与归属上下文——经 config.configurable 注入，不进 state。"""

    session: AsyncSession
    user_id: uuid.UUID
    session_id: uuid.UUID


class GraphState(TypedDict):
    goal: str
    context: str
    plan: list[dict[str, Any]]
    reply: str


def _text_of(message: AIMessage) -> str:
    """模型输出文本可能是分块 content：取文本块拼接 strip。"""
    if isinstance(message.content, str):
        return message.content.strip()
    return "".join(
        block.get("text", "") if isinstance(block, dict) else str(block)
        for block in message.content
    ).strip()


async def _plan(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """调规划模型：取 tool_calls 与文本回复（plan 只含 tool/params，run_id 由 dispatch 并入）。"""
    model = planner()
    message: AIMessage = await model.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT + state["context"]),
            HumanMessage(content=state["goal"]),
        ]
    )
    plan = [{"tool": call["name"], "params": call["args"]} for call in message.tool_calls]
    return {"plan": plan, "reply": _text_of(message)}


async def _verify(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """对每步 spec_of + validate；任何一步失败 → plan 清空、reply 换「执行不了」话术。"""
    for step in state["plan"]:
        try:
            spec_of(step["tool"])
        except UnknownTool:
            reason = f"没有名为 {step['tool']} 的工具"
            break
        try:
            tools.validate(step["tool"], step["params"])
        except tools.InvalidParams as error:
            reason = str(error)
            break
    else:
        return {}
    return {"plan": [], "reply": f"这一步暂时执行不了：{reason}"}


def _has_plan(state: GraphState) -> str:
    return "dispatch" if state["plan"] else "end"


async def _dispatch(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """逐步 submit（服务端校验后投递）、把 run_id 并进步骤；reply 为空时补话术。"""
    deps: AgentDeps = config["configurable"]["deps"]
    steps: list[dict[str, Any]] = []
    for step in state["plan"]:
        run = await tools.submit(
            deps.session, deps.user_id, step["tool"], step["params"],
            session_id=deps.session_id,
        )
        steps.append({**step, "run_id": str(run.id)})
    labels = "、".join(label_of(step["tool"]) for step in steps)
    reply = state["reply"] or f"好，正在{labels}。"
    return {"plan": steps, "reply": reply}


@lru_cache
def _build_graph() -> Any:
    """图编译一次（工具签名在绑定时固化）；改 SPECS 或配置的测试须清 planner 缓存重编译。"""
    graph = StateGraph(GraphState)
    graph.add_node("plan", _plan)
    graph.add_node("verify", _verify)
    graph.add_node("dispatch", _dispatch)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "verify")
    graph.add_conditional_edges("verify", _has_plan, {"dispatch": "dispatch", "end": END})
    graph.add_edge("dispatch", END)
    return graph.compile()


async def run(goal: str, context: str, deps: AgentDeps) -> tuple[str, list[dict[str, Any]]]:
    """顶层入口：返回 (reply, plan)；reply 永远非空——兜底链的最后一层。"""
    result = await _build_graph().ainvoke(
        {"goal": goal, "context": context, "plan": [], "reply": ""},
        config={"configurable": {"deps": deps}},
    )
    return result["reply"] or FALLBACK_REPLY, result["plan"]
