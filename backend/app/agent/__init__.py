"""Agent 包：规划模型绑定（llm）与 plan → verify → dispatch 图（graph）。

顶层只暴露 graph.run 一个入口；deps 走 config.configurable，不进 state。
"""
from app.agent.graph import AgentDeps, run

__all__ = ["AgentDeps", "run"]
