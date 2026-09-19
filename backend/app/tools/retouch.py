"""两个像素工具：先拍平画布再做 PIL 运算，走队列（秒级重运算 + 进度上报）。

去背景白底拍平（四角抠图需要角上有确定参照色）、调色透明底拍平（保透明区
不被白污染）。产出直接采用为当前图（adopt_asset_id）——用户点「去背景」要的
就是当前图的处理结果，再让用户去墙里点一次是多余动作。
"""
import asyncio

from pydantic import BaseModel, Field

from app.edits import pixels
from app.edits.pixels import MattingError
from app.edits.render import TRANSPARENT
from app.models.asset import AssetKind, AssetSource
from app.services import assets as assets_service
from app.services import runs
from app.tools.base import ToolSpec
from app.tools.context import ToolError, flatten_session, require_session


class RemoveBackgroundIn(BaseModel):
    """无参工具：保留空模型让注册表三界（校验/签名/面板）形态一致。"""


class AdjustIn(BaseModel):
    """11 参数全部可选（缺省 0 = 不生效），两界共用这一份定义。"""

    brightness: float = Field(default=0, ge=-1, le=1)
    contrast: float = Field(default=0, ge=-1, le=1)
    highlights: float = Field(default=0, ge=-1, le=1)
    shadows: float = Field(default=0, ge=-1, le=1)
    temperature: float = Field(default=0, ge=-1, le=1)
    tint: float = Field(default=0, ge=-1, le=1)
    saturation: float = Field(default=0, ge=-1, le=1)
    vibrance: float = Field(default=0, ge=-1, le=1)
    sharpness: float = Field(default=0, ge=-1, le=1)
    clarity: float = Field(default=0, ge=-1, le=1)
    vignette: float = Field(default=0, ge=0, le=1)


async def remove_background(session, run) -> dict:
    row = await require_session(session, run)
    await runs.report(session, run, 20, "识别主体")
    flat = await flatten_session(session, row)  # 白底：给四角抠图提供参照色
    try:
        result = await asyncio.to_thread(pixels.remove_background, flat)
    except MattingError as error:
        raise ToolError(str(error)) from None
    await runs.report(session, run, 50, "去除背景")
    asset = await assets_service.create_from_bytes(
        session, run.user_id, result, kind=AssetKind.subject, source=AssetSource.tool
    )
    asset_id = str(asset.id)
    return {"asset_ids": [asset_id], "adopt_asset_id": asset_id}


async def adjust_image(session, run) -> dict:
    row = await require_session(session, run)
    await runs.report(session, run, 20, "读取画布")
    flat = await flatten_session(session, row, background=TRANSPARENT)  # 透明底：保透明区干净
    await runs.report(session, run, 60, "调整色彩")
    params = AdjustIn.model_validate(run.params)
    result = await asyncio.to_thread(pixels.adjust, flat, **params.model_dump())
    asset = await assets_service.create_from_bytes(
        session, run.user_id, result, kind=AssetKind.generated, source=AssetSource.tool
    )
    asset_id = str(asset.id)
    return {"asset_ids": [asset_id], "adopt_asset_id": asset_id}


REMOVE_BACKGROUND = ToolSpec(
    name="remove_background",
    label="去背景",
    description="去除当前图片的纯色背景，保留主体（透明底）",
    params=RemoveBackgroundIn,
    handler=remove_background,
    session_required=True,
)
ADJUST_IMAGE = ToolSpec(
    name="adjust_image",
    label="调色",
    description="对当前图片做确定性调色：亮度、对比度、高光、阴影、色温、色调、"
    "饱和度、自然饱和度、锐化、清晰度、晕影",
    params=AdjustIn,
    handler=adjust_image,
    session_required=True,
)
