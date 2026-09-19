"""工具注册表：三界契约的单一来源。

新增工具只改两处：写一个 spec 模块 + 在 SPECS 加一行；
校验（services.tools.validate）、模型签名（agent.llm）、
前端工具栏（api/sessions.ts 的 ACTION_LABELS 手工同步）都从这份元组生成。
"""
from app.tools.base import ToolSpec, UnknownTool
from app.tools.canvas import (
    CROP_CANVAS,
    FLIP_LAYER,
    REORDER_LAYER,
    ROTATE_LAYER,
    SCALE_LAYER,
    SET_LAYER_OPACITY,
)
from app.tools.enhance import EXPAND_CANVAS, REPLACE_BACKGROUND, UPSCALE_IMAGE
from app.tools.generate import GENERATE_IMAGE
from app.tools.region import ERASE_REGION, REPLACE_REGION
from app.tools.retouch import ADJUST_IMAGE, REMOVE_BACKGROUND

# 注册表最终顺序与命名（S13 十四工具：选区两工具插在 adjust_image 之后、crop_canvas 之前）
SPECS: tuple[ToolSpec, ...] = (
    GENERATE_IMAGE,
    REPLACE_BACKGROUND,
    EXPAND_CANVAS,
    UPSCALE_IMAGE,
    REMOVE_BACKGROUND,
    ADJUST_IMAGE,
    ERASE_REGION,
    REPLACE_REGION,
    CROP_CANVAS,
    FLIP_LAYER,
    SET_LAYER_OPACITY,
    REORDER_LAYER,
    SCALE_LAYER,
    ROTATE_LAYER,
)


def spec_of(name: str) -> ToolSpec:
    """未知名抛 UnknownTool——模型幻觉出的工具名在这里被挡下。"""
    for spec in SPECS:
        if spec.name == name:
            return spec
    raise UnknownTool(name)


def label_of(name: str) -> str:
    """注册表文案；未知名回退原名（落库的 tool 字符串永远可读）。"""
    try:
        return spec_of(name).label
    except UnknownTool:
        return name
