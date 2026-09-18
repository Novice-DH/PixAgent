"""编辑会话契约：建改入参 + 摘要/详情/历史出参。

签名 URL 永不落库：wall 内 AssetOut.of() 每次现算。PATCH 只认
title / current_asset_id 两个可选字段，未提供（exclude_unset）= 不修改。
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.layers import LayerDocument
from app.models.asset import Asset
from app.models.edit_history import EditHistory
from app.models.edit_session import EditSession
from app.schemas.asset import AssetOut
from app.storage import signed_url

MAX_WALL_ASSETS = 12


class SessionCreateIn(BaseModel):
    current_asset_id: uuid.UUID
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_WALL_ASSETS)
    title: str | None = None


class SessionPatchIn(BaseModel):
    """均可空均可选；显式 null 与未提供都视为不修改（空对象 {} = 零变化）。"""

    title: str | None = None
    current_asset_id: uuid.UUID | None = None


class SessionOut(BaseModel):
    """列表摘要：不含 document。"""

    id: uuid.UUID
    title: str
    revision: int
    current_asset_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WallAssetOut(BaseModel):
    position: int
    asset: AssetOut


class SessionDetailOut(SessionOut):
    document: LayerDocument
    wall: list[WallAssetOut]

    @classmethod
    def of(cls, row: EditSession, wall: list[WallAssetOut]) -> "SessionDetailOut":
        return cls(
            id=row.id,
            title=row.title,
            revision=row.revision,
            current_asset_id=row.current_asset_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            document=LayerDocument.model_validate(row.document),
            wall=wall,
        )


def wall_out(position: int, asset: Asset) -> WallAssetOut:
    out = WallAssetOut(position=position, asset=AssetOut.model_validate(asset))
    out.asset.url = signed_url(asset.storage_key)
    return out


class HistoryOut(BaseModel):
    seq: int
    action: str
    params: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime

    @classmethod
    def of(cls, row: EditHistory) -> "HistoryOut":
        return cls(
            seq=row.seq,
            action=row.action,
            params=row.params,
            result=row.result,
            created_at=row.created_at,
        )
