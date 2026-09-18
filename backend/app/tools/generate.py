"""generate_image 工具登记：注册表的第一个条目。

description 是给规划模型的取向说明：修改现有图片的编辑类工具后续期接入，
别让规划模型拿生图工具硬凑"修改"类指令。
"""
from app.schemas.run import GenerateIn
from app.services import generation
from app.tools.base import ToolSpec

GENERATE_IMAGE = ToolSpec(
    name="generate_image",
    label="生成图片",
    description="从零生成图片候选；没有可编辑图片或明确要全新画面时使用，修改现有图片不要用它",
    params=GenerateIn,
    handler=generation.execute,
    agent_hidden=("seed", "reference_asset_ids"),
)
