"""图片校验原语：格式以解码结果为准——扩展名与 Content-Type 是可伪造的客户端输入。

probe 是纯函数：完整解码暴露截断/损坏数据，自设像素上限 + Pillow 防解压炸弹
双保险；一切失败坍缩为同一条「文件已损坏或不是受支持的图片」，由路由翻译 422。
"""
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIN_EDGE_PX = 32
MAX_PIXELS = 50_000_000

REJECTED_MESSAGE = "文件已损坏或不是受支持的图片"

# 解码格式名 → 存储扩展名（与前端 ACCEPTED_TYPES 白名单语义一致）
FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

# 透明通道判定宁滥勿缺：LA/PA 与调色板 transparency 同样携带 alpha（调色发黑的前置防线）
_ALPHA_MODES = frozenset({"RGBA", "LA", "PA"})


class ImageRejected(Exception):
    """文件已损坏或不是受支持的图片。"""


@dataclass(frozen=True)
class ImageMeta:
    image_format: str  # PIL 解码格式名：JPEG / PNG / WEBP
    width: int
    height: int
    has_alpha: bool

    @property
    def extension(self) -> str:
        return FORMAT_EXTENSIONS[self.image_format]


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in _ALPHA_MODES or "transparency" in img.info


def probe(data: bytes) -> ImageMeta:
    """校验并提取图片元信息：先看头（格式/尺寸，拦解压炸弹），再完整解码（拦截断/损坏）。

    Pillow 的 DecompressionBombError 在 open() 阶段即可抛出（读 IHDR 声明尺寸），
    且不是 OSError 子类——两段 try 都按"一切异常坍缩为 ImageRejected"处理。
    """
    if not data:
        raise ImageRejected(REJECTED_MESSAGE)

    try:
        img = Image.open(BytesIO(data))
    except Exception:
        # UnidentifiedImageError / DecompressionBombError / OSError 等统一坍缩
        raise ImageRejected(REJECTED_MESSAGE) from None

    try:
        image_format = img.format
        width, height = img.size
        if image_format not in FORMAT_EXTENSIONS:
            raise ImageRejected(REJECTED_MESSAGE)
        if min(width, height) < MIN_EDGE_PX:
            raise ImageRejected(REJECTED_MESSAGE)
        if width * height > MAX_PIXELS:
            raise ImageRejected(REJECTED_MESSAGE)
        # 完整解码：只读文件头会放过截断/损坏数据
        img.load()
        alpha = _has_alpha(img)
    except ImageRejected:
        raise
    except Exception:
        # OSError（截断）、DecompressionBombError（load 阶段阈值）等统一坍缩
        raise ImageRejected(REJECTED_MESSAGE) from None
    finally:
        img.close()

    return ImageMeta(image_format=image_format, width=width, height=height, has_alpha=alpha)
