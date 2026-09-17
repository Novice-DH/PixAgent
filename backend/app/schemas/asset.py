"""素材进出契约：AssetOut.of() 统一组装含现算签名 URL 的响应。"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.asset import Asset, AssetKind, AssetSource
from app.storage import signed_url


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: AssetKind
    source: AssetSource
    image_format: str
    width: int
    height: int
    size_bytes: int
    has_alpha: bool
    created_at: datetime
    url: str = ""  # 签名 URL 永不落库，由 of() 每次现算填充

    @classmethod
    def of(cls, asset: Asset) -> "AssetOut":
        out = cls.model_validate(asset)
        out.url = signed_url(asset.storage_key)
        return out
