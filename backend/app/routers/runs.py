"""生图任务路由：协议与状态码翻译；受理只做校验、落 run、投队列三件事。"""
import uuid

import redis.exceptions
from fastapi import APIRouter, HTTPException, status

from app import queue
from app.db import SessionDep
from app.deps import CurrentUser
from app.schemas.run import GenerateIn, RunOut
from app.services import assets as assets_service
from app.services import runs

router = APIRouter(tags=["runs"])

GENERATE_TOOL = "generate_image"


@router.post(
    "/generations",
    response_model=RunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_generation(
    payload: GenerateIn, user: CurrentUser, session: SessionDep
) -> RunOut:
    # 受理期先挡一次参考图越权/不存在（Worker 侧再兜一层 ProviderError）
    for asset_id in payload.reference_asset_ids:
        if await assets_service.get_for_user(session, user.id, asset_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="参考图不存在"
            )

    try:
        run = await runs.create(session, user.id, GENERATE_TOOL, payload.to_params())
        await queue.enqueue("generate_images", run.id)
    except redis.exceptions.RedisError:
        # 队列不可达是环境故障而非用户错误：503 而不是 500，API 进程不崩
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="队列服务暂时不可用，请稍后再试",
        ) from None
    return await RunOut.of(session, run)


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> RunOut:
    run = await runs.get_for_user(session, user.id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return await RunOut.of(session, run)
