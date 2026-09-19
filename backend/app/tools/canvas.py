"""六个文档工具：只改 LayerDocument 的确定性变换，queued=False 同步执行。

公共模式：require_session → document_of → edits.document.<fn> → 返回
{"document": 新文档}；落库与快照由统一外壳的 _record 走 apply_edit。
layer_id 对 Agent 隐藏（agent_hidden）：缺省由 resolve_layer 在服务端解析为
最上层可见图像层，模型说"翻转图片"即可，永远不需要知道图层 ID 的存在。
"""
from pydantic import BaseModel, Field, model_validator

from app.edits import document as edits_document
from app.edits.document import EditError
from app.layers import LayerDocument, LayerMissing, resolve_layer
from app.ratios import Ratio
from app.tools.base import ToolSpec
from app.tools.context import ToolError, current_document, require_session

MIN_CROP = 32


class LayerRef(BaseModel):
    """文档工具公共参数基类：layer_id 由界面点选传入，Agent 侧恒缺省。"""

    layer_id: str | None = None


class FlipIn(LayerRef):
    direction: str = Field(pattern="^(horizontal|vertical)$")


class SetOpacityIn(LayerRef):
    opacity: float = Field(ge=0, le=1)


class ReorderIn(LayerRef):
    place: str = Field(pattern="^(top|bottom|up|down)$")


class ScaleIn(LayerRef):
    factor: float | None = Field(default=None, gt=0, le=8)
    scale_x: float | None = Field(default=None, gt=0, le=8)
    scale_y: float | None = Field(default=None, gt=0, le=8)

    @model_validator(mode="after")
    def _at_least_one(self) -> "ScaleIn":
        if self.factor is None and self.scale_x is None and self.scale_y is None:
            raise ValueError("factor 与 scale_x/scale_y 至少给其一")
        return self


class RotateIn(LayerRef):
    angle: float | None = Field(default=None, ge=-360, le=360)
    rotation: float | None = Field(default=None, ge=-360, le=360)

    @model_validator(mode="after")
    def _at_least_one(self) -> "RotateIn":
        if self.angle is None and self.rotation is None:
            raise ValueError("angle 与 rotation 至少给其一")
        return self


class CropRect(BaseModel):
    """归一化裁剪矩形：0–1 且不出画布（浮点容差 1.0001）。"""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _within_canvas(self) -> "CropRect":
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("裁剪矩形超出画布")
        return self


class CropIn(LayerRef):
    ratio: Ratio | None = None
    rect: CropRect | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "CropIn":
        if (self.ratio is None) == (self.rect is None):
            raise ValueError("ratio 与 rect 恰给其一")
        return self


async def _edited_document(session, run, apply) -> dict:
    """文档工具公共骨架：装载会话 → 解析目标层 → 应用纯函数变换。"""
    row = await require_session(session, run)
    document = current_document(row)
    try:
        new_document: LayerDocument = apply(document)
    except (EditError, LayerMissing) as error:
        raise ToolError(str(error)) from None
    return {"document": new_document.model_dump(mode="json")}


async def flip_layer(session, run) -> dict:
    params = FlipIn.model_validate(run.params)

    def apply(document: LayerDocument):
        layer = resolve_layer(document, params.layer_id)
        return edits_document.flip(document, layer.id, direction=params.direction)

    return await _edited_document(session, run, apply)


async def set_layer_opacity(session, run) -> dict:
    params = SetOpacityIn.model_validate(run.params)

    def apply(document: LayerDocument):
        layer = resolve_layer(document, params.layer_id)
        return edits_document.set_opacity(document, layer.id, params.opacity)

    return await _edited_document(session, run, apply)


async def reorder_layer(session, run) -> dict:
    params = ReorderIn.model_validate(run.params)

    def apply(document: LayerDocument):
        layer = resolve_layer(document, params.layer_id)
        return edits_document.reorder(document, layer.id, place=params.place)

    return await _edited_document(session, run, apply)


async def scale_layer(session, run) -> dict:
    params = ScaleIn.model_validate(run.params)

    def apply(document: LayerDocument):
        layer = resolve_layer(document, params.layer_id)
        return edits_document.scale(
            document,
            layer.id,
            factor=params.factor,
            scale_x=params.scale_x,
            scale_y=params.scale_y,
        )

    return await _edited_document(session, run, apply)


async def rotate_layer(session, run) -> dict:
    params = RotateIn.model_validate(run.params)

    def apply(document: LayerDocument):
        layer = resolve_layer(document, params.layer_id)
        return edits_document.rotate(
            document, layer.id, angle=params.angle, rotation=params.rotation
        )

    return await _edited_document(session, run, apply)


async def crop_canvas(session, run) -> dict:
    params = CropIn.model_validate(run.params)

    def apply(document: LayerDocument):
        rect = (
            (params.rect.x, params.rect.y, params.rect.width, params.rect.height)
            if params.rect
            else None
        )
        return edits_document.crop(document, ratio=params.ratio, rect=rect)

    return await _edited_document(session, run, apply)


HIDDEN = ("layer_id",)

CROP_CANVAS = ToolSpec(
    name="crop_canvas",
    label="裁剪",
    description="把画布裁剪为指定比例（1:1、4:5、9:16、16:9、3:4）或指定归一化矩形区域",
    params=CropIn,
    handler=crop_canvas,
    agent_hidden=HIDDEN,
    queued=False,
    session_required=True,
)
FLIP_LAYER = ToolSpec(
    name="flip_layer",
    label="翻转",
    description="把当前图片水平或垂直镜像翻转",
    params=FlipIn,
    handler=flip_layer,
    agent_hidden=HIDDEN,
    queued=False,
    session_required=True,
)
SET_LAYER_OPACITY = ToolSpec(
    name="set_layer_opacity",
    label="透明度",
    description="设置当前图层的不透明度（0 到 1 之间的小数）",
    params=SetOpacityIn,
    handler=set_layer_opacity,
    agent_hidden=HIDDEN,
    queued=False,
    session_required=True,
)
REORDER_LAYER = ToolSpec(
    name="reorder_layer",
    label="图层顺序",
    description="调整图层叠放顺序：置顶、置底、上移一层或下移一层",
    params=ReorderIn,
    handler=reorder_layer,
    agent_hidden=HIDDEN,
    queued=False,
    session_required=True,
)
SCALE_LAYER = ToolSpec(
    name="scale_layer",
    label="缩放",
    description="缩放当前图层：按倍数相对缩放，或分别指定横向纵向缩放倍数",
    params=ScaleIn,
    handler=scale_layer,
    agent_hidden=HIDDEN,
    queued=False,
    session_required=True,
)
ROTATE_LAYER = ToolSpec(
    name="rotate_layer",
    label="旋转",
    description="旋转当前图层：在当前角度上继续转（angle），或设置到固定角度（rotation）",
    params=RotateIn,
    handler=rotate_layer,
    agent_hidden=HIDDEN,
    queued=False,
    session_required=True,
)
