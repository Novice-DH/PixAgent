"""像素运算：调色与去背景的确定性 PIL 运算。

调色全程带 alpha 通道（项目不变式）：通道分离用 split/merge 取纯 RGB、
运算完成 putalpha 回填——convert("RGB") 会把透明像素与黑色混合，
透明底商品图调完透明区发黑。像素级重运算由工具层用 asyncio.to_thread 包装，
不阻塞事件循环。
"""
import io
import math

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

from app.config import get_settings

# 四角抠图容差：四角平均色的欧氏距离判定（纯色底商品图足够好）
_CORNER_TOLERANCE = 28
_CORNER_SAMPLE = 12  # 每角取样块边长（像素）


class MattingError(Exception):
    """抠图提供方不可用（rembg 被显式指定但依赖缺失等）——工具层翻译为 ToolError。"""


def _clamp8(value: float) -> int:
    return max(0, min(255, round(value)))


def _channel_lut(offset: float) -> list[int]:
    return [_clamp8(level + offset) for level in range(256)]


def _white_balance(red, green, blue, temperature: float, tint: float):
    """白平衡逐通道点算：R +28t、G −20·tint、B −28t+12·tint。"""
    if temperature == 0 and tint == 0:
        return red, green, blue
    red = red.point(_channel_lut(28 * temperature))
    green = green.point(_channel_lut(-20 * tint))
    blue = blue.point(_channel_lut(-28 * temperature + 12 * tint))
    return red, green, blue


def _tone(rgb, shadows: float, highlights: float):
    """tone 曲线：shadows 权重随亮度递减 ×64、highlights 递增 ×64。

    增量是亮度的标量函数：先由亮度图 point 出每像素增量图，再对 RGB 三个
    通道做饱和加/减——等价于逐像素循环，但全部落在 C 层。
    """
    for value, weight_of_luma in (
        (shadows, lambda level: 255 - level),
        (highlights, lambda level: level),
    ):
        if value == 0:
            continue
        luma = rgb.convert("L")
        lut = [round(value * weight_of_luma(level) / 255 * 64) for level in range(256)]
        delta = luma.point(lut)
        bands = list(rgb.split())
        if value > 0:
            bands = [ImageChops.add(band, delta) for band in bands]
        else:
            delta = delta.point(abs)
            bands = [ImageChops.subtract(band, delta) for band in bands]
        rgb = Image.merge("RGB", bands)
    return rgb


def _vibrance(rgb, amount: float):
    """vibrance 按 chroma 反比加权：已鲜艳色少动、灰暗色多动，避免过曝。"""
    if amount == 0:
        return rgb
    bands = rgb.split()
    channel_max = ImageChops.lighter(ImageChops.lighter(bands[0], bands[1]), bands[2])
    channel_min = ImageChops.darker(ImageChops.darker(bands[0], bands[1]), bands[2])
    chroma = ImageChops.subtract(channel_max, channel_min)
    mask = chroma.point(lambda level: round(abs(amount) * (255 - level)))
    enhanced = ImageEnhance.Color(rgb).enhance(1 + amount)
    return Image.composite(enhanced, rgb, mask)


def _clarity(rgb, amount: float):
    """clarity：正值为中半径 USM（radius=2 percent=80x threshold=2），负值向模糊混合。"""
    if amount > 0:
        return rgb.filter(
            ImageFilter.UnsharpMask(radius=2, percent=round(80 * amount), threshold=2)
        )
    return Image.blend(rgb, rgb.filter(ImageFilter.GaussianBlur(2)), -amount)


def _radial_mask(width: int, height: int, amount: float):
    """径向暗角 mask：中心 255 → 角落 255·(1−amount)，幂 1.6；低分辨率构建再放大。"""
    size = 256
    center = (size - 1) / 2
    corner = math.sqrt(2)  # 归一化对角距离：角落 t=1，边中点 t≈0.707
    mask = Image.new("L", (size, size))
    pixels = mask.load()
    for y in range(size):
        for x in range(size):
            dx = (x - center) / center
            dy = (y - center) / center
            t = math.sqrt(dx * dx + dy * dy) / corner
            pixels[x, y] = max(0, round(255 * (1 - amount * t**1.6)))
    return mask.resize((width, height), Image.Resampling.BILINEAR)


def _vignette(rgb, amount: float):
    """晕影：径向 mask 与 RGB 做通道级乘法（ImageChops.multiply）。"""
    mask = _radial_mask(*rgb.size, amount)
    return ImageChops.multiply(rgb, Image.merge("RGB", (mask, mask, mask)))


def adjust(
    data: bytes,
    *,
    brightness: float = 0.0,
    contrast: float = 0.0,
    highlights: float = 0.0,
    shadows: float = 0.0,
    temperature: float = 0.0,
    tint: float = 0.0,
    saturation: float = 0.0,
    vibrance: float = 0.0,
    sharpness: float = 0.0,
    clarity: float = 0.0,
    vignette: float = 0.0,
) -> bytes:
    """11 参数调色：全部 −1..1（晕影 0..1），0 值不产生效果；输出 PNG 保 alpha。"""
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    alpha = image.getchannel("A")
    red, green, blue = image.split()[:3]
    red, green, blue = _white_balance(red, green, blue, temperature, tint)
    rgb = _tone(Image.merge("RGB", (red, green, blue)), shadows, highlights)
    if brightness:
        rgb = ImageEnhance.Brightness(rgb).enhance(1 + brightness)
    if contrast:
        rgb = ImageEnhance.Contrast(rgb).enhance(1 + contrast)
    rgb = _vibrance(rgb, vibrance)
    if saturation:
        rgb = ImageEnhance.Color(rgb).enhance(1 + saturation)
    if clarity:
        rgb = _clarity(rgb, clarity)
    if sharpness:
        rgb = ImageEnhance.Sharpness(rgb).enhance(1 + sharpness)
    if vignette:
        rgb = _vignette(rgb, vignette)

    # alpha 原样回填：全部 RGB 运算不触碰透明通道
    out = Image.merge("RGBA", (*rgb.split(), alpha))
    buffer = io.BytesIO()
    out.save(buffer, format="PNG")
    return buffer.getvalue()


def remove_background(data: bytes) -> bytes:
    """按 MATTING_PROVIDER 分派：auto=有 rembg 用之否则四角；rembg=强求；corner=四角。

    显式指定的 provider 不静默降级——用户点名 rembg 却得到 corner 是最难排查的
    "假成功"；只有 auto 才做运行时 ImportError 探测降级。
    """
    provider = get_settings().matting_provider
    if provider == "corner":
        return _corner_matting(data)
    if provider == "rembg":
        return _rembg_matting(data)
    if provider == "auto":
        try:
            return _rembg_matting(data)
        except MattingError:
            return _corner_matting(data)
    raise MattingError(f"未知的 MATTING_PROVIDER：{provider}")


def _rembg_matting(data: bytes) -> bytes:
    try:
        from rembg import remove
    except ImportError as error:
        raise MattingError(
            "rembg 未安装：请安装可选依赖组 cv（uv sync --extra cv），"
            "或将 MATTING_PROVIDER 设为 auto / corner"
        ) from error
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    buffer = io.BytesIO()
    remove(image).save(buffer, format="PNG")
    return buffer.getvalue()


def _corner_matting(data: bytes) -> bytes:
    """四角抠图：四角平均色为参照色，欧氏距离 ≤ 容差的像素清为透明。"""
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    width, height = image.size
    sample = min(_CORNER_SAMPLE, width, height)
    corners = (
        image.crop((0, 0, sample, sample)),
        image.crop((width - sample, 0, width, sample)),
        image.crop((0, height - sample, sample, height)),
        image.crop((width - sample, height - sample, width, height)),
    )
    totals = [0, 0, 0]
    counted = 0
    for corner in corners:
        raw = corner.tobytes()  # RGBA 四字节一组；getdata 在新版 Pillow 已弃用
        for offset in range(0, len(raw), 4):
            red, green, blue, alpha = raw[offset : offset + 4]
            if alpha == 0:
                continue
            totals[0] += red
            totals[1] += green
            totals[2] += blue
            counted += 1
    reference = (255, 255, 255) if counted == 0 else tuple(value // counted for value in totals)

    pixels = image.load()
    limit_sq = _CORNER_TOLERANCE**2
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            distance_sq = (red - reference[0]) ** 2 + (green - reference[1]) ** 2 + (
                blue - reference[2]
            ) ** 2
            if distance_sq <= limit_sq:
                pixels[x, y] = (red, green, blue, 0)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
