"""图层文档领域模块：LayerDocument 是画布当前状态的权威描述。

后续所有编辑工具只修改这份文档，像素合成由渲染环节按文档执行；
文档以 JSONB 随 edit_sessions 持久化，刷新可恢复。缩放是倍率不是像素，
视图层的缩放（看多大）在 stores/canvasView.ts，永不写入文档。
"""
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.asset import Asset


class LayerKind(StrEnum):
    image = "image"
    text = "text"
    shape = "shape"


class Transform(BaseModel):
    """图层形变：x/y 为画布坐标偏移，scale 为倍率，rotation 为角度。"""

    x: float = 0
    y: float = 0
    scale_x: float = 1
    scale_y: float = 1
    rotation: float = 0


class Layer(BaseModel):
    id: str
    kind: LayerKind
    name: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    asset_id: str | None = None
    transform: Transform = Field(default_factory=Transform)
    opacity: float = Field(default=1, ge=0, le=1)
    visible: bool = True
    locked: bool = False


class LayerDocument(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    layers: list[Layer]


BASE_LAYER_ID = "base"
BASE_LAYER_NAME = "底图"


def document_of(asset: Asset) -> LayerDocument:
    """画布语义级起点：画布尺寸 = 资产尺寸，单层锁定底图。

    切换图片是画布语义级变化（画幅都变了），所以文档永远整体重建而不是打补丁；
    text / shape 层与拆层都只是后续往这份文档里加层换层，结构本期一次定稳。
    """
    return LayerDocument(
        width=asset.width,
        height=asset.height,
        layers=[
            Layer(
                id=BASE_LAYER_ID,
                kind=LayerKind.image,
                name=BASE_LAYER_NAME,
                width=asset.width,
                height=asset.height,
                asset_id=str(asset.id),
                locked=True,
            )
        ],
    )
