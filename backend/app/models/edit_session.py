"""EditSession 模型：编辑会话 + 当前画布文档；SessionAsset 复合主键关联表（图片墙）。

会话指向资产用 RESTRICT——画布正指着这张图，资产不许静默消失；
删用户才级联清会话，删会话才级联清墙。级联方向 = 依赖方向。
session_assets 是"全模型 UUIDBase"惯例的显式例外：自然键 (session_id, asset_id)
已经唯一，代理 UUID 列只会多一个索引和一次 join 间接（纯关联表豁免，例外已记录在 PROJECT_FACTS）。
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDBase


class EditSession(UUIDBase):
    __tablename__ = "edit_sessions"
    # 撤销指针的推进是同请求内的 UPDATE：eager_defaults 让 onupdate 的
    # updated_at 经 RETURNING 随语句取回，避免同事务后续访问触发隐式刷新
    # （AsyncSession 下隐式刷新抛 MissingGreenlet）。
    __mapper_args__ = {"eager_defaults": True}

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(80))
    original_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT")
    )
    current_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT")
    )
    # 失效信号不是版本号：只在切换到不同资产时 +1，旧 revision 上的选区/遮罩视为失效
    revision: Mapped[int] = mapped_column(Integer, default=1)
    # 撤销指针：当前所处历史位置；seq 分配从 history_seq+1 走，截断重做后与 max(seq) 分离
    history_seq: Mapped[int] = mapped_column(Integer, default=0)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # 列表倒序键：项目基类无此列，就地声明，写法与 tool_run 时间列同风格
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SessionAsset(Base):
    """会话图片墙：未采用的候选一并留存，随时切回而不是丢弃。

    同事务插入的多行时间戳相同，顺序稳定靠显式 position（同事务多行取 max+1 递增）。
    """

    __tablename__ = "session_assets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edit_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)
