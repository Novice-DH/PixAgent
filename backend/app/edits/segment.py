"""点选分割：SAM 会话与 embedding 缓存 + corner 圆形兜底。

分派沿用抠图纪律（pixels.remove_background 同款）：corner 纯兜底、rembg 强求
不静默降级、auto 运行时失败降级。SAM 路径是一次编码多次解码的经济学：编码贵、
解码便宜，embedding 按原始图片字节的 sha256 缓存（LRU 上限 4——单 embedding
MB 级内存的预算），连续点选同一张图只编码一次，「第二次点击秒回」。

张量装配复用 rembg sam 会话的工具函数（warp_affine / apply_coords /
get_input_points / transform_masks / _predict_encoder / _predict_decoder），
随 rembg 版本走，属方向性实现——契约是行为（点选→物体级遮罩）、缓存键
（原始字节哈希）与降级链，不是逐行张量代码；版本变动时只需适配 _encode /
_decode 两个函数。rembg 在可选组 cv，未安装时本模块照常导入（SAM 相关导入
全部惰性发生在函数内），corner 路径零依赖可用。CI 经 corner_matting 夹具
不触发 SAM。
"""
import hashlib
import io
import threading
from collections import OrderedDict
from typing import Any

from PIL import Image, ImageDraw

from app.config import get_settings
from app.edits.mask import overlay_png

# 编码输入的内部形状（宽 684 × 高 1024，随 rembg sam 会话约定）
_INNER_SIZE = (684, 1024)
# embedding LRU 预算：键是原始图片字节的 sha256——resize 或重编码后的
# 「等价图」不共享缓存（宁可重算不可错配），上限 4 是内存预算
_EMBEDDING_CACHE_LIMIT = 4
# corner 兜底圆半径：短边 16% 且下限 16px——比例化 + 下限让任何尺寸都有可点面积
_CORNER_RADIUS_RATIO = 0.16
_CORNER_RADIUS_MIN = 16


class SegmentError(Exception):
    """点选分割提供方不可用（rembg 被显式指定但失败等）——工具层翻译为 ToolError。"""


_embedding_cache: "OrderedDict[str, Any]" = OrderedDict()
_cache_lock = threading.Lock()
_session: Any = None
_session_lock = threading.Lock()


def segment_points(image: bytes, points: list[tuple[float, float]]) -> bytes:
    """归一化点 → 物体遮罩 overlay PNG；无点返回空遮罩。分派纪律同抠图。"""
    provider = get_settings().matting_provider
    if provider == "corner":
        return _corner_points(image, points)
    if provider == "rembg":
        return _sam_points(image, points)
    if provider == "auto":
        try:
            return _sam_points(image, points)
        except Exception:
            return _corner_points(image, points)
    raise SegmentError(f"未知的 MATTING_PROVIDER：{provider}")


def _corner_points(image: bytes, points: list[tuple[float, float]]) -> bytes:
    """零依赖兜底：点击处画圆（多圆 union）——职责是流程完整，不是分割质量。"""
    width, height = Image.open(io.BytesIO(image)).size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    radius = max(_CORNER_RADIUS_MIN, int(min(width, height) * _CORNER_RADIUS_RATIO))
    for nx, ny in points:
        cx, cy = round(nx * width), round(ny * height)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
    return overlay_png(mask)


def _sam_points(image: bytes, points: list[tuple[float, float]]) -> bytes:
    """SAM 路径：先查 embedding 缓存（未命中才编码），再按全部点跑一次解码。

    多点提示是联合语义（多点共同框定一个物体），点选追加=全部 markers 一次性
    重解码，不是逐点分割再 union。输出 >0.0 的像素打包为 255 的 L 遮罩。
    """
    sam = _import_sam()
    session = _get_session()

    key = hashlib.sha256(image).hexdigest()
    with _cache_lock:
        embedding = _embedding_cache.get(key)
        if embedding is not None:
            _embedding_cache.move_to_end(key)
    if embedding is None:
        embedding = _encode(sam, session, image)
        with _cache_lock:
            _embedding_cache[key] = embedding
            while len(_embedding_cache) > _EMBEDDING_CACHE_LIMIT:
                _embedding_cache.popitem(last=False)

    width, height = Image.open(io.BytesIO(image)).size
    pixel_points = [(nx * width, ny * height) for nx, ny in points]
    return _decode(sam, session, embedding, pixel_points, (width, height))


def _get_session() -> Any:
    """SAM 会话惰性单例：模型只加载一次，线程锁防并发重复加载。"""
    global _session
    with _session_lock:
        if _session is None:
            from rembg import new_session

            _session = new_session("sam")
        return _session


def _import_sam() -> Any:
    """rembg sam 会话模块：工具函数随版本走，接口不匹配抛 SegmentError——
    auto 分派据此降级 corner，rembg 显式指定则如实失败。"""
    try:
        from rembg.sessions import sam as sam_module
    except ImportError as error:
        raise SegmentError(
            "rembg 未安装：请安装可选依赖组 cv（uv sync --extra cv），"
            "或将 MATTING_PROVIDER 设为 auto / corner"
        ) from error
    required = ("get_input_points", "_predict_encoder", "_predict_decoder")
    missing = [name for name in required if not hasattr(sam_module, name)]
    if missing:
        raise SegmentError(f"rembg sam 会话接口变动，缺少 {', '.join(missing)}")
    return sam_module


def _encode(sam: Any, session: Any, image: bytes) -> Any:
    """编码：原始图片字节 → embedding（无返回值缓存，缓存由调用方管理）。

    张量装配随 rembg 版本走：warp_affine 缩放到内部形状、_predict_encoder 出
    embedding；接口变动时改这里。
    """
    import numpy as np
    from PIL import Image as PILImage

    source = PILImage.open(io.BytesIO(image)).convert("RGB")
    # warp_affine 等价物：等比缩放 + 居中贴到内部形状画布
    scale = min(_INNER_SIZE[0] / source.width, _INNER_SIZE[1] / source.height)
    scaled = source.resize(
        (round(source.width * scale), round(source.height * scale)),
        Image.Resampling.BILINEAR,
    )
    canvas = PILImage.new("RGB", _INNER_SIZE)
    canvas.paste(
        scaled,
        ((_INNER_SIZE[0] - scaled.width) // 2, (_INNER_SIZE[1] - scaled.height) // 2),
    )
    array = np.asarray(canvas).astype(np.float32)
    input_name = getattr(session, "input_name", "images")  # 版本适配点
    return sam._predict_encoder(session, input_name, list(_INNER_SIZE), array)


def _decode(
    sam: Any,
    session: Any,
    embedding: Any,
    pixel_points: list[tuple[float, float]],
    original_size: tuple[int, int],
) -> bytes:
    """解码：embedding + 点提示 → overlay PNG。归一化点已在调用方转像素坐标，
    喂给模型前经 apply_coords 类变换（rembg 工具函数内部处理）；低分辨率 logits
    经 transform_masks 类工具放回原尺寸（函数内部或此处适配）。"""
    import numpy as np

    prompts = [
        {"type": "point", "data": [x, y], "label": 1} for x, y in pixel_points
    ]
    input_points = np.asarray(sam.get_input_points(prompts), dtype=np.float32)
    input_labels = np.ones(len(input_points), dtype=np.float32)
    masks = sam._predict_decoder(session, embedding, input_points, input_labels)
    return overlay_png(_masks_to_luma(masks, original_size))


def _masks_to_luma(masks: Any, size: tuple[int, int]) -> Image.Image:
    """解码输出 → L 遮罩：>0.0 即选中，打包为 255；尺寸不符 NEAREST 对齐。"""
    import numpy as np

    array = np.asarray(masks)
    if array.ndim == 3:  # (1, h, w) → (h, w)
        array = array[0]
    luma = Image.fromarray((array > 0.0).astype(np.uint8) * 255, mode="L")
    if luma.size != size:
        luma = luma.resize(size, Image.Resampling.NEAREST)
    return luma
