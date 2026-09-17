"""UUIDBase：所有业务模型的抽象基类（UUID 主键 + created_at）。

UUID 主键不可枚举，且多期多表工程中迁移合并不会键位冲突；
禁止自增整型主键。必须挂在本项目 Base 声明体系下，
保证 Alembic autogenerate 经 Base.metadata 发现全部表。
"""
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

from app.db import Base


class UUIDBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def enum_column(
    enum_cls: type[StrEnum], *, name: str | None = None, **kwargs: Any
) -> MappedColumn[Any]:
    """枚举列统一入口：VARCHAR(16) 存值、非 PG 原生枚举、不建约束——

    增删取值是改代码，不是 ALTER TYPE 迁移；name 仅作元数据标识（DB 侧是普通 VARCHAR）。
    """
    return mapped_column(
        SAEnum(
            enum_cls,
            name=name or enum_cls.__name__.lower(),
            values_callable=lambda cls: [member.value for member in cls],
            native_enum=False,
            length=16,
        ),
        **kwargs,
    )
