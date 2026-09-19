"""拍平合成：LayerDocument + 图层像素 → 合成画布图像。

与服务端几何约定一处定义：x/y 是未缩放框的左上角，尺寸取 width × |scale|、
按符号 mirror/flip，旋转绕图层中心（Pillow 逆时针为正、画布约定顺时针为正，
取负）——前端 Konva 的中心原点渲染是同一条规则的另一次实现，两端必须逐像素一致。
"""
import io

from PIL import Image, ImageOps

from app.layers import LayerDocument, LayerKind

WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def flatten(document: LayerDocument, images: dict[str, bytes], *, background=WHITE) -> Image.Image:
    """按层表顺序合成（末尾层视觉最前）；background 白底或透明底。

    images 以 layer.asset_id 为键提供图层原始字节；缺失的图层跳过。
    paste 前按画布边界裁剪——裁剪工具"只平移图层"的像素级裁剪由此自然完成。
    """
    canvas = Image.new("RGBA", (document.width, document.height), background)
    for layer in document.layers:
        if layer.kind != LayerKind.image or not layer.visible or not layer.asset_id:
            continue
        raw = images.get(layer.asset_id)
        if raw is None:
            continue
        image = Image.open(io.BytesIO(raw)).convert("RGBA")
        scale_x, scale_y = layer.transform.scale_x, layer.transform.scale_y
        target = (
            max(1, round(layer.width * abs(scale_x))),
            max(1, round(layer.height * abs(scale_y))),
        )
        if scale_x < 0:
            image = ImageOps.mirror(image)
        if scale_y < 0:
            image = ImageOps.flip(image)
        image = image.resize(target, Image.Resampling.LANCZOS)
        if layer.opacity < 1:
            alpha = image.getchannel("A")
            opacity = layer.opacity
            image.putalpha(alpha.point(lambda value, _opacity=opacity: round(value * _opacity)))
        if layer.transform.rotation:
            image = image.rotate(
                -layer.transform.rotation, expand=True, resample=Image.Resampling.BICUBIC
            )

        center_x = layer.transform.x + layer.width / 2
        center_y = layer.transform.y + layer.height / 2
        left = round(center_x - image.width / 2)
        top = round(center_y - image.height / 2)
        clip_left, clip_top = max(left, 0), max(top, 0)
        clip_right = min(left + image.width, document.width)
        clip_bottom = min(top + image.height, document.height)
        if clip_right > clip_left and clip_bottom > clip_top:
            source = image.crop(
                (clip_left - left, clip_top - top, clip_right - left, clip_bottom - top)
            )
            canvas.alpha_composite(source, (clip_left, clip_top))
    return canvas
