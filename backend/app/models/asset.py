"""Asset 模型：素材元数据，字节在对象存储。

分类枚举一次铺满路线图词汇表，本期只消费 original/upload——
就位 ≠ 启用，后续期次只新增写入方，不做 schema 演进。
"""
import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, enum_column


class AssetKind(StrEnum):
    original = "original"
    generated = "generated"
    subject = "subject"
    background = "background"
    mask = "mask"
    marketing = "marketing"
    export = "export"


class AssetSource(StrEnum):
    upload = "upload"
    generate = "generate"
    tool = "tool"


class Asset(UUIDBase):
    __tablename__ = "assets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[AssetKind] = enum_column(AssetKind, name="asset_kind")
    source: Mapped[AssetSource] = enum_column(AssetSource, name="asset_source")
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    image_format: Mapped[str] = mapped_column(String(8))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    has_alpha: Mapped[bool] = mapped_column(Boolean)
