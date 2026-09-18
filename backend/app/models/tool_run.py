"""ToolRun 模型：所有工具执行的通用记录（本期 generate_image，编辑类工具复用同一状态机）。

status/progress/stage 与 SSE 进度协议一一对应；retries 本期保留不消费；
result 记 JSONB（generate_image 落 asset_ids），error 记对外可透出的失败原因。
"""
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, enum_column


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"

    @property
    def is_terminal(self) -> bool:
        """终态判定：后三值不可再转移（worker 重启重投靠它短路）。"""
        return self in _TERMINAL_STATUSES


_TERMINAL_STATUSES = frozenset(
    {RunStatus.succeeded, RunStatus.failed, RunStatus.canceled}
)


class ToolRun(UUIDBase):
    __tablename__ = "tool_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # 会话内工具调用才有值；创作页直发的生图为 None（常态不是异常，不强造匿名会话）
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edit_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tool: Mapped[str] = mapped_column(String(48))
    status: Mapped[RunStatus] = enum_column(RunStatus, default=RunStatus.queued)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
