"""文档变换：只改 LayerDocument 的确定性运算，全部返回深拷贝后的新文档。

翻转是负缩放不是像素镜像（零成本、天然可逆）；裁剪只平移图层（像素裁剪由
渲染时画布边界自然完成）；x/y 是未缩放框的左上角，负缩放不移动中心——
渲染端与服务端共享这一个几何模型。
"""
import math

from app.layers import Layer, LayerDocument, LayerMissing
from app.ratios import Ratio, parts_of

MIN_CROP = 32  # 与上传校验的最短边一致：裁出更小的画布后续链路不接受


class EditError(Exception):
    """参数合法但画布不适用（如裁剪过小）——工具层翻译为 ToolError。"""


def _target(document: LayerDocument, layer_id: str) -> Layer:
    for layer in document.layers:
        if layer.id == layer_id:
            return layer
    raise LayerMissing(f"图层 {layer_id} 不存在或不可编辑")


def flip(document: LayerDocument, layer_id: str, *, direction: str) -> LayerDocument:
    """水平/垂直翻转 = 对应轴 scale 取负；x/y 不动，中心不位移。"""
    new = document.model_copy(deep=True)
    layer = _target(new, layer_id)
    if direction == "horizontal":
        layer.transform.scale_x = -layer.transform.scale_x
    elif direction == "vertical":
        layer.transform.scale_y = -layer.transform.scale_y
    else:
        raise EditError(f"未知翻转方向：{direction}")
    return new


def set_opacity(document: LayerDocument, layer_id: str, opacity: float) -> LayerDocument:
    """透明度是绝对值赋值，不是相对增减。"""
    new = document.model_copy(deep=True)
    _target(new, layer_id).opacity = opacity
    return new


def scale(
    document: LayerDocument,
    layer_id: str,
    *,
    factor: float | None = None,
    scale_x: float | None = None,
    scale_y: float | None = None,
) -> LayerDocument:
    """factor 相对乘；scale_x/scale_y 绝对赋值但保留原符号（已翻转层保持翻转）。"""
    new = document.model_copy(deep=True)
    transform = _target(new, layer_id).transform
    if factor is not None:
        transform.scale_x *= factor
        transform.scale_y *= factor
    if scale_x is not None:
        transform.scale_x = math.copysign(scale_x, transform.scale_x)
    if scale_y is not None:
        transform.scale_y = math.copysign(scale_y, transform.scale_y)
    return new


def rotate(
    document: LayerDocument,
    layer_id: str,
    *,
    angle: float | None = None,
    rotation: float | None = None,
) -> LayerDocument:
    """angle 相对加（现值缺省 0）；rotation 绝对赋值。"""
    new = document.model_copy(deep=True)
    transform = _target(new, layer_id).transform
    if angle is not None:
        transform.rotation = transform.rotation + angle
    if rotation is not None:
        transform.rotation = rotation
    return new


def reorder(document: LayerDocument, layer_id: str, *, place: str) -> LayerDocument:
    """top/bottom 移端、up/down 相邻交换；层表末尾为视觉最前（up = 向列表末尾移动）。"""
    new = document.model_copy(deep=True)
    index = next((i for i, layer in enumerate(new.layers) if layer.id == layer_id), None)
    if index is None:
        raise LayerMissing(layer_id)
    if place == "top":
        new.layers.append(new.layers.pop(index))
    elif place == "bottom":
        new.layers.insert(0, new.layers.pop(index))
    elif place == "up":
        if index < len(new.layers) - 1:
            new.layers[index], new.layers[index + 1] = new.layers[index + 1], new.layers[index]
    elif place == "down":
        if index > 0:
            new.layers[index], new.layers[index - 1] = new.layers[index - 1], new.layers[index]
    else:
        raise EditError(f"未知排序动作：{place}")
    return new


def crop(
    document: LayerDocument,
    *,
    ratio: Ratio | None = None,
    rect: tuple[float, float, float, float] | None = None,
) -> LayerDocument:
    """裁剪画布：ratio 居中适配或 rect 归一化换算 → 像素取整裁边 → MIN_CROP 校验。

    只平移图层 transform.x/y（不改图层像素、不改图层尺寸）——像素级裁剪由
    渲染时画布边界自然完成；画布宽高改为裁剪尺寸。
    """
    if (ratio is None) == (rect is None):
        raise EditError("ratio 与 rect 必须恰给其一")

    if ratio is not None:
        ratio_w, ratio_h = parts_of(ratio)
        target = ratio_w / ratio_h
        if document.width / document.height > target:
            crop_w = document.height * target
            crop_h = float(document.height)
        else:
            crop_w = float(document.width)
            crop_h = document.width / target
        x0 = (document.width - crop_w) / 2
        y0 = (document.height - crop_h) / 2
        left, top = math.ceil(x0), math.ceil(y0)
        right, bottom = math.floor(x0 + crop_w), math.floor(y0 + crop_h)
    else:
        rx, ry, rw, rh = rect
        left, top = round(rx * document.width), round(ry * document.height)
        right, bottom = round((rx + rw) * document.width), round((ry + rh) * document.height)

    left, top = max(left, 0), max(top, 0)
    right, bottom = min(right, document.width), min(bottom, document.height)
    width, height = right - left, bottom - top
    if width < MIN_CROP or height < MIN_CROP:
        raise EditError(f"裁剪尺寸过小，画布每边至少 {MIN_CROP}px")

    new = document.model_copy(deep=True)
    for layer in new.layers:
        layer.transform.x -= left
        layer.transform.y -= top
    new.width, new.height = width, height
    return new
