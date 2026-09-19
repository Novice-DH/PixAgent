"""遮罩纯函数：选区可视化、笔刷光栅化与「保内换外」合成。

遮罩即资产、着色即协议：overlay_png 产出的品牌色 RGBA PNG 既是持久化资产
又是前端叠加的直接素材——前端只调透明度，不重复实现遮罩渲染。形状信息在
alpha 里（to_luma 取 alpha 不取亮度），颜色只是给人看的。像素级调用方一律
asyncio.to_thread 包装。
"""
import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# 选区着色（前端叠加的品牌色）：语义等价的表层素材，单点定义
HIGHLIGHT_COLOR = (95, 152, 173)
# 合成边界羽化半径：硬边会像贴膏药，轻微高斯模糊让新旧像素过渡自然
FEATHER_RADIUS = 1.2


def to_luma(data: bytes, size: tuple[int, int]) -> Image.Image:
    """遮罩字节 → L 模式形状图：RGBA/LA 取 alpha 通道（形状在 alpha 里），
    其余转 L；尺寸不符 NEAREST 重采样——形状对齐不需要插值平滑。"""
    image = Image.open(io.BytesIO(data))
    if image.mode in ("RGBA", "LA", "PA"):
        luma = image.getchannel("A")
    else:
        luma = image.convert("L")
    if luma.size != size:
        luma = luma.resize(size, Image.Resampling.NEAREST)
    return luma


def overlay_png(mask: Image.Image) -> bytes:
    """L 形状图 → 选区可视化 RGBA PNG：选中处着色不透明、其余全透明。"""
    if mask.mode != "L":
        mask = mask.convert("L")
    alpha = mask.point(lambda level: 255 if level > 0 else 0)
    solid = Image.new("RGB", mask.size, HIGHLIGHT_COLOR)
    overlay = Image.merge("RGBA", (*solid.split(), alpha))
    buffer = io.BytesIO()
    overlay.save(buffer, format="PNG")
    return buffer.getvalue()


def rasterize_strokes(
    size: tuple[int, int],
    strokes: list[list[tuple[float, float]]],
    *,
    radius: float,
    base: Image.Image | None = None,
) -> Image.Image:
    """笔迹 → L 遮罩（像素坐标）。多于 2 个点的笔画先 polygon 闭合填充——
    用户圈一个环时心里选中的是「圈内」；再画轮廓带兜底（线 + 逐点圆），
    自相交乱涂涂过必中。两点只画带子、单点只画圆。base 非空时 union
    （笔刷追加是自由形状叠加，lighter 就是正确语义）。"""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    width = max(2, int(min(size) * radius))
    for stroke in strokes:
        points = [(round(x), round(y)) for x, y in stroke]
        if not points:
            continue
        if len(points) > 2:
            draw.polygon(points, fill=255)
        if len(points) >= 2:
            draw.line(points, fill=255, width=width, joint="curve")
            if len(points) > 2:
                _dot_points(draw, points, width)
        else:
            _dot_points(draw, points, width)
    if base is not None:
        if base.mode != "L":
            base = base.convert("L")
        if base.size != size:
            base = base.resize(size, Image.Resampling.NEAREST)
        mask = ImageChops.lighter(mask, base)
    return mask


def _dot_points(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], width: int) -> None:
    """逐点圆：线端封口 + 自相交处必中（线宽的一半为半径）。"""
    r = width / 2
    for x, y in points:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


def apply_masked(source: bytes, edited: bytes, mask: bytes) -> bytes:
    """「保内换外」合成：选区内像素取编辑结果、选区外逐字节保持原图。

    模型编辑整张图，边界由我们画——luma 遮罩羽化后 composite，模型在选区外
    的任何漂移都被丢弃。edited 尺寸不符先 LANCZOS 对齐（生成端点可能微调画幅）。
    """
    source_image = Image.open(io.BytesIO(source)).convert("RGBA")
    edited_image = Image.open(io.BytesIO(edited)).convert("RGBA")
    if edited_image.size != source_image.size:
        edited_image = edited_image.resize(source_image.size, Image.Resampling.LANCZOS)
    luma = to_luma(mask, source_image.size).filter(ImageFilter.GaussianBlur(FEATHER_RADIUS))
    merged = Image.composite(edited_image, source_image, luma)
    buffer = io.BytesIO()
    merged.save(buffer, format="PNG")
    return buffer.getvalue()
