"""UUIDBase：所有业务模型的抽象基类（UUID 主键 + created_at）。

UUID 主键不可枚举，且多期多表工程中迁移合并不会键位冲突；
禁止自增整型主键。必须挂在本项目 Base 声明体系下，
保证 Alembic autogenerate 经 Base.metadata 发现全部表。
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UUIDBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
