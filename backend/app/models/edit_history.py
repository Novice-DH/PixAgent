"""EditHistory 模型：线性编辑记录（滚动保留最近 HISTORY_LIMIT 条）。

明确放弃版本树：历史是"给用户看的操作流水 + 给后续工具期的动作记录"，
不是存证系统。seq 取 max+1，(session_id, seq) 唯一约束兜底并发——
应用层的 max 查询有竞态窗口，数据库唯一约束是最后一道闸。
"""
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase

HISTORY_LIMIT = 20


class EditHistory(UUIDBase):
    __tablename__ = "edit_history"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_edit_history_session_seq"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edit_sessions.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(48))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
