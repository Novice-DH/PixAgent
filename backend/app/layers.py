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


class LayerMissing(Exception):
    """目标图层不存在或不可编辑——工具层翻译为 ToolError，直接展示给用户。"""


def resolve_layer(document: LayerDocument, layer_id: str | None = None) -> Layer:
    """图层目标解析单点：显式 id 精确命中；缺省取最上层可见图像层。

    Agent 与界面共用同一缺省规则——模型不知道图层 ID 的存在（agent_hidden），
    说"翻转图片"由服务端决定翻哪层；界面点选后才显式传 id。层表末尾为视觉最前。
    """
    if layer_id is not None:
        for layer in document.layers:
            if layer.id == layer_id:
                if layer.kind != LayerKind.image:
                    raise LayerMissing(f"图层 {layer_id} 不存在或不可编辑")
                return layer
        raise LayerMissing(f"图层 {layer_id} 不存在或不可编辑")
    for layer in reversed(document.layers):
        if layer.kind == LayerKind.image and layer.visible:
            return layer
    raise LayerMissing("画布上没有可编辑的图像图层")


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
