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
