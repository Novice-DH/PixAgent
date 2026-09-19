"""三个生成式工具：换背景/扩图/超分——复用确定性工具期的全部骨架，增量只有调模型。

公共骨架：require_session → 白底拍平 → 阶段锚点 → Provider 编辑调用（进度直通
runs.report）→ 产出逐张落 generated 素材 → 按采用策略返回。采用策略按 count
分层是代码行为不是开关：单张输出就是用户点名要的结果（adopt，revision+1、
可撤销）；多张输出是备选集，全进图片墙不采用（revision 不变），挑选权归用户。
换背景的约束前缀拼在服务端——界面与 Agent 共用同一保护，不存在绕过面。
"""
from pydantic import BaseModel, Field

from app.models.asset import AssetKind, AssetSource
from app.providers import EditRequest, get_image_provider
from app.ratios import Ratio, cover_size
from app.services import assets as assets_service
from app.services import runs
from app.tools.base import ToolSpec
from app.tools.context import current_document, flatten_session, require_session

# 服务端单点的模型硬约束 framing：防"换背景"被理解成"重新生成整张图"
_BACKGROUND_PREFIX = "只替换背景，保持主体、光线和边缘不变。新背景：{prompt}"


class ReplaceBackgroundIn(BaseModel):
    """换背景：prompt 必填，count 决定采用策略（单张直接采用，多张进墙点选）。"""

    prompt: str = Field(min_length=1, max_length=500)
    count: int = Field(default=1, ge=1, le=4)
    negative_prompt: str | None = None


class ExpandCanvasIn(BaseModel):
    """扩图：目标比例必填；prompt 缺省用自然延伸——目标画幅必须包住原画。"""

    ratio: Ratio
    prompt: str = Field(
        default="自然延伸画面边缘，保持主体完整", min_length=1, max_length=500
    )


class UpscaleImageIn(BaseModel):
    """超分：2–4 倍等比放大，提高分辨率不改变构图。"""

    scale: int = Field(default=2, ge=2, le=4)


def _progress(session, run):
    """Provider 进度回调直通 runs.report——单调性由服务端收口（取 max 兜底）。"""

    async def on_progress(progress: int, stage: str) -> None:
        await runs.report(session, run, progress, stage)

    return on_progress


async def _store(session, run, images: list[bytes]) -> list[str]:
    """产出逐张落自有存储：模型侧字节是临时的，落库后图片墙才有稳定签名 URL。"""
    return [
        str(
            (
                await assets_service.create_from_bytes(
                    session, run.user_id, image, kind=AssetKind.generated, source=AssetSource.tool
                )
            ).id
        )
        for image in images
    ]


async def replace_background(session, run) -> dict:
    row = await require_session(session, run)
    await runs.report(session, run, 15, "读取画布")
    flat = await flatten_session(session, row)
    await runs.report(session, run, 30, "生成新背景")

    params = ReplaceBackgroundIn.model_validate(run.params)
    images = await get_image_provider().edit(
        EditRequest(
            prompt=_BACKGROUND_PREFIX.format(prompt=params.prompt),
            image=flat,
            count=params.count,
            negative_prompt=params.negative_prompt,
        ),
        _progress(session, run),
    )
    asset_ids = await _store(session, run, images)
    if params.count > 1:
        # 多候选是备选集：自动采用等于替用户做审美决定，只进墙（revision 不变）
        await runs.report(session, run, 95, "候选已加入图片墙，点选采用")
        return {"asset_ids": asset_ids}
    return {"asset_ids": asset_ids, "adopt_asset_id": asset_ids[0]}


async def expand_canvas(session, run) -> dict:
    row = await require_session(session, run)
    await runs.report(session, run, 15, "读取画布")
    flat = await flatten_session(session, row)
    await runs.report(session, run, 30, "延伸画幅")

    params = ExpandCanvasIn.model_validate(run.params)
    # 目标画幅刚好包住原画：短边向比例靠拢、原边不动，主体零裁切
    document = current_document(row)
    width, height = cover_size(document.width, document.height, params.ratio)
    images = await get_image_provider().edit(
        EditRequest(prompt=params.prompt, image=flat, count=1, width=width, height=height),
        _progress(session, run),
    )
    asset_ids = await _store(session, run, images)
    return {"asset_ids": asset_ids, "adopt_asset_id": asset_ids[0]}


async def upscale_image(session, run) -> dict:
    row = await require_session(session, run)
    await runs.report(session, run, 15, "读取画布")
    flat = await flatten_session(session, row)
    await runs.report(session, run, 30, "提升分辨率")

    params = UpscaleImageIn.model_validate(run.params)
    result = await get_image_provider().upscale(flat, params.scale, _progress(session, run))
    asset_ids = await _store(session, run, [result])
    return {"asset_ids": asset_ids, "adopt_asset_id": asset_ids[0]}


REPLACE_BACKGROUND = ToolSpec(
    name="replace_background",
    label="换背景",
    description="把当前图片的背景替换为描述的新场景，主体保持不变",
    params=ReplaceBackgroundIn,
    handler=replace_background,
    agent_hidden=("negative_prompt",),
    session_required=True,
)
EXPAND_CANVAS = ToolSpec(
    name="expand_canvas",
    label="扩图",
    description="把画布扩展到目标比例：自然延伸画面边缘，主体不被裁切",
    params=ExpandCanvasIn,
    handler=expand_canvas,
    session_required=True,
)
UPSCALE_IMAGE = ToolSpec(
    name="upscale_image",
    label="超分",
    description="把当前图片等比放大并提升清晰度（2-4 倍），不改变内容",
    params=UpscaleImageIn,
    handler=upscale_image,
    session_required=True,
)
