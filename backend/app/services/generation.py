"""生成服务：Worker 侧执行编排——参考图 → Provider → 候选落库 → 终态。

候选走素材期同一条 create_from_bytes 链路落 MinIO 与 assets 表（kind=generated），
数据库只记 asset_ids——所有"URL"都是视图，资产只有对象存储里的字节。
"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_run import ToolRun
from app.providers import GenerateRequest, ProviderError, get_image_provider
from app.ratios import Ratio, size_for
from app.services import assets as assets_service
from app.services import runs
from app.storage import get_object

logger = logging.getLogger(__name__)

UNEXPECTED_FAILURE_MESSAGE = "生成失败，请重试"


async def execute(session: AsyncSession, run: ToolRun) -> None:
    """执行一次生图：入口假定 run 处于可执行状态（终态短路由任务函数负责）。"""
    params = run.params
    try:
        await runs.start(session, run)

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
        await runs.finish_succeeded(session, run, {"asset_ids": asset_ids})
    except ProviderError as error:
        await runs.finish_failed(session, run, str(error))
    except Exception:
        # 未预期异常：细节只进日志，对外统一话术——堆栈不该出现在 UI
        logger.exception("生成执行未预期失败 run=%s tool=%s", run.id, run.tool)
        await runs.finish_failed(session, run, UNEXPECTED_FAILURE_MESSAGE)


async def _collect_references(session: AsyncSession, run: ToolRun) -> list[bytes]:
    """参考图从自有对象存储读取字节；缺失/非本人一律 ProviderError（路由在受理期先挡一次）。"""
    references: list[bytes] = []
    for raw_id in run.params.get("reference_asset_ids") or []:
        asset = await assets_service.get_for_user(session, run.user_id, uuid.UUID(raw_id))
        if asset is None:
            raise ProviderError("参考图不存在")
        references.append(await get_object(asset.storage_key))
    return references
