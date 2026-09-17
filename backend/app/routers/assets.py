"""素材路由：协议与状态码翻译；校验规则在 services/images，业务规则在 services/assets。"""
import uuid
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.db import SessionDep
from app.deps import CurrentUser
from app.schemas.asset import AssetOut
from app.services.assets import create_from_bytes, get_for_user, list_for_user
from app.services.images import MAX_UPLOAD_BYTES, ImageRejected

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    user: CurrentUser,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> AssetOut:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件超过 20 MB 上限"
        )
    try:
        asset = await create_from_bytes(session, user.id, data)
    except ImageRejected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="文件已损坏或不是受支持的图片"
        ) from None
    except (ClientError, BotoCoreError):
        # 对象存储不可达/报错是环境故障而非用户错误：503 而不是 500
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="存储服务暂时不可用，请稍后再试"
        ) from None
    return AssetOut.of(asset)


@router.get("", response_model=list[AssetOut])
async def list_assets(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AssetOut]:
    assets = await list_for_user(session, user.id, limit)
    return [AssetOut.of(asset) for asset in assets]


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> AssetOut:
    asset = await get_for_user(session, user.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    return AssetOut.of(asset)
