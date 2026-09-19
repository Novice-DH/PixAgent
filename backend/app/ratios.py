"""比例体系：枚举与像素映射——生成尺寸与交付尺寸对齐，避免生成后二次重采样。"""
from enum import StrEnum


class Ratio(StrEnum):
    ONE_ONE = "1:1"
    FOUR_FIVE = "4:5"
    THREE_FOUR = "3:4"
    NINE_SIXTEEN = "9:16"
    SIXTEEN_NINE = "16:9"


RATIO_SIZES: dict[Ratio, tuple[int, int]] = {
    Ratio.ONE_ONE: (1080, 1080),
    Ratio.FOUR_FIVE: (1080, 1350),
    Ratio.THREE_FOUR: (1080, 1440),
    Ratio.NINE_SIXTEEN: (1080, 1920),
    Ratio.SIXTEEN_NINE: (1920, 1080),
}

# 交付三比例：营销物料导出期消费（画布/导出期挂点）
DELIVERY_RATIOS: frozenset[Ratio] = frozenset(
    {Ratio.ONE_ONE, Ratio.FOUR_FIVE, Ratio.NINE_SIXTEEN}
)


def size_for(ratio: Ratio) -> tuple[int, int]:
    """比例 → (宽, 高)；未知比例由 Pydantic 枚举校验在入口拦截。"""
    return RATIO_SIZES[ratio]


def parts_of(ratio: Ratio) -> tuple[int, int]:
    """比例 → (宽比, 高比) 原子对；裁剪居中适配按纵横比计算，不用像素尺寸。"""
    parts = {
        Ratio.ONE_ONE: (1, 1),
        Ratio.FOUR_FIVE: (4, 5),
        Ratio.THREE_FOUR: (3, 4),
        Ratio.NINE_SIXTEEN: (9, 16),
        Ratio.SIXTEEN_NINE: (16, 9),
    }
    return parts[ratio]


def cover_size(width: int, height: int, ratio: Ratio) -> tuple[int, int]:
    """刚好包住原图的目标比例画幅（扩图语义：主体零裁切）。

    短边向比例靠拢、原边不动：两分支按 width×rh 与 height×rw 整数比较决定动
    哪条边，整除取整，各边 max(1)；等比时两分支同值（原样不动）。
    扩图用它而不是生图标准尺寸——标准尺寸服务"从零生成"，套在扩图上要么
    裁主体要么重采样变形。
    """
    ratio_width, ratio_height = parts_of(ratio)
    if width * ratio_height < height * ratio_width:
        return max(1, height * ratio_width // ratio_height), height
    return width, max(1, width * ratio_height // ratio_width)
