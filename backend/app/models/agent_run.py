"""AgentRun 模型：一轮对话（goal→reply→steps）的持久化记录。

与 ToolRun 是两层抽象：一轮对话与一次工具执行生命周期不同、失败语义不同
（规划失败 vs 执行失败）、消费端不同（对话列表 vs 进度卡）——合成一张表会让
"规划失败"污染执行状态机。status 只表示规划本身成败；无论规划成败都落一条，
"说了话就该有回音"。plan 落库形态 [{"tool","params","run_id"}]，校验被拒时为
空数组；revision 记录规划时的会话修订号（规划基准，未来执行期判定画布过期）。
"""
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, enum_column
from app.models.tool_run import RunStatus


class AgentRun(UUIDBase):
    __tablename__ = "agent_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edit_sessions.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    goal: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    status: Mapped[RunStatus] = enum_column(RunStatus)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
