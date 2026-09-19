"""edits 纯函数层测试：文档变换 / 拍平合成 / 像素运算，全部内存直算。

透明通道三条（调色保 alpha、透明底拍平、晕影乘法）与四角抠图是本期
不变式的钉子用例；几何用例（翻转/裁剪/旋转）钉住两端共享的坐标模型。
"""
import io
import uuid

import pytest
from PIL import Image

from app.edits import document, pixels, render
from app.edits.pixels import MattingError
from app.layers import (
    BASE_LAYER_ID,
    Layer,
    LayerDocument,
    LayerKind,
    LayerMissing,
    Transform,
    resolve_layer,
)
from app.ratios import Ratio


def _solid(width: int, height: int, color: tuple[int, ...]) -> bytes:
    image = Image.new("RGBA", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _layer(
    layer_id: str = BASE_LAYER_ID, width: int = 100, height: int = 100, **transform
) -> Layer:
    return Layer(
        id=layer_id,
        kind=LayerKind.image,
        name=layer_id,
        width=width,
        height=height,
        asset_id=str(uuid.uuid4()),
        transform=Transform(**transform) if transform else Transform(),
    )


def _doc(width: int = 100, height: int = 100, layers: list[Layer] | None = None) -> LayerDocument:
    return LayerDocument(width=width, height=height, layers=layers or [_layer()])


def _pixels(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _pixel_at(image: Image.Image, x: int, y: int) -> tuple[int, ...]:
    return image.getpixel((x, y))


# ---------- 文档变换 ----------


def test_flip_negates_scale_and_keeps_center():
    doc = _doc(layers=[_layer(width=200, x=100, y=50)])
    flipped = document.flip(doc, BASE_LAYER_ID, direction="horizontal")
    layer = flipped.layers[0]
    assert layer.transform.scale_x == -1
    assert (layer.transform.x, layer.transform.y) == (100, 50)  # 中心不位移
    assert doc.layers[0].transform.scale_x == 1  # 原文档不被就地修改


def test_flip_vertical_negates_scale_y():
    doc = _doc(layers=[_layer()])
    flipped = document.flip(doc, BASE_LAYER_ID, direction="vertical")
    assert flipped.layers[0].transform.scale_y == -1
    assert flipped.layers[0].transform.scale_x == 1


def test_scale_relative_preserves_flip_direction():
    doc = _doc(layers=[_layer(scale_x=-1, scale_y=-1)])
    scaled = document.scale(doc, BASE_LAYER_ID, factor=2)
    assert scaled.layers[0].transform.scale_x == -2
    assert scaled.layers[0].transform.scale_y == -2


def test_scale_absolute_preserves_sign():
    doc = _doc(layers=[_layer(scale_x=-1)])
    scaled = document.scale(doc, BASE_LAYER_ID, scale_x=3)
    assert scaled.layers[0].transform.scale_x == -3  # 已翻转层保持翻转


def test_scale_absolute_positive_stays_positive():
    doc = _doc(layers=[_layer(scale_x=2)])
    scaled = document.scale(doc, BASE_LAYER_ID, scale_x=3, scale_y=0.5)
    assert (scaled.layers[0].transform.scale_x, scaled.layers[0].transform.scale_y) == (3, 0.5)


def test_rotate_relative_and_absolute():
    doc = _doc(layers=[_layer(rotation=10)])
    assert document.rotate(doc, BASE_LAYER_ID, angle=80).layers[0].transform.rotation == 90
    assert document.rotate(doc, BASE_LAYER_ID, rotation=45).layers[0].transform.rotation == 45
    fresh = _doc(layers=[_layer()])
    assert document.rotate(fresh, BASE_LAYER_ID, angle=-30).layers[0].transform.rotation == -30


def test_set_opacity_is_absolute():
    doc = _doc(layers=[_layer()])
    doc.layers[0].opacity = 0.8
    assert document.set_opacity(doc, BASE_LAYER_ID, 0.5).layers[0].opacity == 0.5


def test_reorder_four_directions():
    layers = [_layer(f"l{i}") for i in range(4)]  # 层表末尾为视觉最前
    doc = _doc(layers=layers)
    assert [layer.id for layer in document.reorder(doc, "l0", place="top").layers] == [
        "l1", "l2", "l3", "l0",
    ]
    assert [layer.id for layer in document.reorder(doc, "l3", place="bottom").layers] == [
        "l3", "l0", "l1", "l2",
    ]
    assert [layer.id for layer in document.reorder(doc, "l1", place="up").layers] == [
        "l0", "l2", "l1", "l3",
    ]
    assert [layer.id for layer in document.reorder(doc, "l1", place="down").layers] == [
        "l1", "l0", "l2", "l3",
    ]
    assert [layer.id for layer in document.reorder(doc, "l3", place="up").layers] == [
        "l0", "l1", "l2", "l3",
    ]  # 已在最前：no-op


def test_crop_ratio_centers_and_translates_layers():
    doc = _doc(width=1920, height=1080, layers=[_layer(width=1920, height=1080, x=500, y=100)])
    cropped = document.crop(doc, ratio=Ratio.ONE_ONE)
    assert (cropped.width, cropped.height) == (1080, 1080)
    layer = cropped.layers[0]
    assert layer.transform.x == 500 - 420  # (1920-1080)/2 = 420
    assert layer.transform.y == 100


def test_crop_ratio_taller_canvas():
    doc = _doc(width=1080, height=1080)
    cropped = document.crop(doc, ratio=Ratio.FOUR_FIVE)
    assert (cropped.width, cropped.height) == (864, 1080)  # 居中适配，向内取整


def test_crop_rect_normalized():
    doc = _doc(width=1080, height=1080, layers=[_layer(width=1080, height=1080, x=270)])
    cropped = document.crop(doc, rect=(0.25, 0.5, 0.5, 0.25))
    assert (cropped.width, cropped.height) == (540, 270)
    assert cropped.layers[0].transform.x == 0


def test_crop_min_limit_raises():
    doc = _doc(width=1080, height=1080)
    with pytest.raises(document.EditError):
        document.crop(doc, rect=(0.0, 0.0, 0.02, 0.02))


def test_crop_requires_exactly_one():
    doc = _doc()
    with pytest.raises(document.EditError):
        document.crop(doc)
    with pytest.raises(document.EditError):
        document.crop(doc, ratio=Ratio.ONE_ONE, rect=(0, 0, 0.5, 0.5))


def test_unknown_layer_raises():
    with pytest.raises(LayerMissing):
        document.flip(_doc(), "nope", direction="horizontal")


def test_resolve_layer_defaults_to_topmost_visible_image():
    hidden = _layer("hidden")
    hidden.visible = False
    text = Layer(id="t", kind=LayerKind.text, name="t", width=10, height=10)
    bottom = _layer("bottom")
    doc = _doc(layers=[hidden, text, bottom])
    assert resolve_layer(doc).id == "bottom"  # 倒序找 kind=image 且 visible
    assert resolve_layer(doc, "hidden").id == "hidden"  # 显式 id 精确命中
    with pytest.raises(LayerMissing):
        resolve_layer(doc, "nope")
    all_hidden = _doc(layers=[hidden])
    with pytest.raises(LayerMissing):
        resolve_layer(all_hidden)


# ---------- 拍平合成 ----------


def test_flatten_negative_scale_mirrors():
    # 左半红右半蓝
    image = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    for x in range(50, 100):
        for y in range(100):
            image.putpixel((x, y), (0, 0, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    half = buffer.getvalue()

    asset_id = str(uuid.uuid4())
    doc = _doc(layers=[_layer(width=100, height=100)])
    doc.layers[0].asset_id = asset_id
    flat = render.flatten(doc, {asset_id: half}, background=render.TRANSPARENT)
    assert _pixel_at(flat, 10, 50)[:3] == (255, 0, 0)  # 未翻转：红在左
    mirror = document.flip(doc, BASE_LAYER_ID, direction="horizontal")
    flat = render.flatten(mirror, {asset_id: half}, background=render.TRANSPARENT)
    assert _pixel_at(flat, 10, 50)[:3] == (0, 0, 255)  # 翻转后蓝在左：负缩放按符号镜像


def test_flatten_crops_to_canvas_bounds_and_respects_opacity():
    asset_id = str(uuid.uuid4())
    doc = _doc(width=100, height=100, layers=[_layer(width=200, height=200, x=-50, y=-50)])
    doc.layers[0].asset_id = asset_id
    doc.layers[0].opacity = 0.5
    flat = render.flatten(doc, {asset_id: _solid(200, 200, (255, 0, 0, 255))})
    red, green, blue, alpha = _pixel_at(flat, 0, 0)
    assert (red, green, blue, alpha) == (255, 127, 127, 255)  # 红色半透明盖在白底上
    assert flat.size == (100, 100)  # 溢出画布部分被裁


def test_flatten_transparent_background_stays_transparent():
    asset_id = str(uuid.uuid4())
    doc = _doc(width=100, height=100, layers=[_layer(width=100, height=100)])
    doc.layers[0].asset_id = asset_id
    # 图层中心挖一个透明洞
    image = Image.new("RGBA", (100, 100), (0, 200, 0, 255))
    for x in range(40, 60):
        for y in range(40, 60):
            image.putpixel((x, y), (0, 200, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    flat = render.flatten(doc, {asset_id: buffer.getvalue()}, background=render.TRANSPARENT)
    assert _pixel_at(flat, 50, 50)[3] == 0  # 透明洞保持透明
    assert _pixel_at(flat, 5, 5)[3] == 255


def test_flatten_rotation_about_center():
    # 左上角贴红的方块旋转 90°（顺时针）后，红应出现在右上角
    asset_id = str(uuid.uuid4())
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(0, 50):
        for y in range(0, 50):
            image.putpixel((x, y), (255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    doc = _doc(width=100, height=100, layers=[_layer(width=100, height=100)])
    doc.layers[0].asset_id = asset_id
    doc.layers[0].transform.rotation = 90
    flat = render.flatten(doc, {asset_id: buffer.getvalue()}, background=render.TRANSPARENT)
    assert _pixel_at(flat, 75, 25)[3] == 255  # 右上象限有内容
    assert _pixel_at(flat, 25, 25)[3] == 0  # 左上象限转空


# ---------- 像素运算 ----------


def test_adjust_keeps_transparency():
    # 左半不透明红、右半全透明：调色后透明区 alpha 仍为 0，不透明区亮度真实变化
    image = Image.new("RGBA", (64, 64), (100, 0, 0, 255))
    for x in range(32, 64):
        for y in range(64):
            image.putpixel((x, y), (200, 0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    out = _pixels(pixels.adjust(buffer.getvalue(), brightness=0.5))
    assert _pixel_at(out, 48, 32)[3] == 0  # 透明区 alpha 原样
    red = _pixel_at(out, 16, 32)
    assert red[0] > 100 and red[1] == 0  # 不透明区被提亮


def test_adjust_brightness_brightens():
    out = _pixels(pixels.adjust(_solid(64, 64, (128, 128, 128, 255)), brightness=0.5))
    assert _pixel_at(out, 32, 32)[0] > 128


def test_adjust_vignette_darkens_corners():
    out = _pixels(pixels.adjust(_solid(64, 64, (200, 200, 200, 255)), vignette=1.0))
    corner = _pixel_at(out, 0, 0)[0]
    center = _pixel_at(out, 32, 32)[0]
    assert corner < 100  # 四角显著变暗
    assert center == 200  # 中心不变


def test_adjust_noop_returns_equivalent_image():
    source = _solid(32, 32, (50, 100, 150, 255))
    out = _pixels(pixels.adjust(source))
    assert _pixel_at(out, 16, 16) == (50, 100, 150, 255)


def test_corner_matting_clears_corners_keeps_subject():
    image = Image.new("RGBA", (64, 64), (0, 200, 0, 255))  # 纯色绿底
    for x in range(20, 44):
        for y in range(20, 44):
            image.putpixel((x, y), (200, 0, 0, 255))  # 红色主体
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    out = _pixels(pixels.remove_background(buffer.getvalue()))
    assert _pixel_at(out, 2, 2)[3] == 0  # 角被清掉
    assert _pixel_at(out, 32, 32)[:3] == (200, 0, 0)  # 主体保留
    assert _pixel_at(out, 32, 32)[3] == 255


def test_remove_background_forced_rembg_without_dependency_raises():
    from app.config import get_settings

    settings = get_settings()
    original = settings.matting_provider
    settings.matting_provider = "rembg"
    try:
        with pytest.raises(MattingError) as error:
            pixels.remove_background(_solid(16, 16, (255, 255, 255, 255)))
        assert "rembg" in str(error.value)
    finally:
        settings.matting_provider = original
