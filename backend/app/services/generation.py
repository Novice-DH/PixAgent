"""生成服务：generate_image 工具的 handler——只做业务，状态机上收 tools.execute。

候选走素材期同一条 create_from_bytes 链路落 MinIO 与 assets 表（kind=generated），
数据库只记 asset_ids——所有"URL"都是视图，资产只有对象存储里的字节。
start/finish/异常兜底由统一外壳负责：ProviderError 在这里照常抛出、由外壳翻译。
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_run import ToolRun
from app.providers import GenerateRequest, ProviderError, get_image_provider
from app.ratios import Ratio, size_for
from app.services import assets as assets_service
from app.services import runs
from app.storage import get_object


async def execute(session: AsyncSession, run: ToolRun) -> dict[str, list[str]]:
    """执行一次生图：只做业务并返回结果字典，不碰状态机。"""
    params = run.params
    width, height = size_for(Ratio(params["ratio"]))
    references = await _collect_references(session, run)

    provider = get_image_provider()

    async def on_progress(progress: int, stage: str) -> None:
        await runs.report(session, run, progress, stage)

    images = await provider.generate(
        GenerateRequest(
            prompt=params["prompt"],
            width=width,
            height=height,
            count=params["count"],
            negative_prompt=params.get("negative_prompt"),
            seed=params.get("seed"),
            references=references,
        ),
        on_progress,
    )

    await runs.report(session, run, 90, "保存候选图")
    asset_ids = [
        str(
            (
                await assets_service.create_from_bytes(
                    session,
                    run.user_id,
                    image,
                    kind=assets_service.AssetKind.generated,
                    source=assets_service.AssetSource.generate,
                )
            ).id
        )
        for image in images
    ]
    return {"asset_ids": asset_ids}


async def _collect_references(session: AsyncSession, run: ToolRun) -> list[bytes]:
    """参考图从自有对象存储读取字节；缺失/非本人一律 ProviderError（路由在受理期先挡一次）。"""
    references: list[bytes] = []
    for raw_id in run.params.get("reference_asset_ids") or []:
        asset = await assets_service.get_for_user(session, run.user_id, uuid.UUID(raw_id))
        if asset is None:
            raise ProviderError("参考图不存在")
        references.append(await get_object(asset.storage_key))
    return references
