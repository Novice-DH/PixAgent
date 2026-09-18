"""素材服务：字节进对象存储、元数据落库；越权防护单一入口。

先存储后落库——两步不可原子，失败停在"孤儿对象"侧（可清理），
避免"死行指向不存在的对象"。主键先生成再拼存储键，两界锚点一一对应。
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetKind, AssetSource
from app.services.images import probe
from app.storage import put_object


async def create_from_bytes(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: bytes,
    kind: AssetKind = AssetKind.original,
    source: AssetSource = AssetSource.upload,
) -> Asset:
    """默认行为是用户上传；生成结果复用同一条落库链路（kind=generated、source=generate）。"""
    meta = probe(data)
    asset_id = uuid.uuid4()
    storage_key = f"users/{user_id}/{asset_id}.{meta.extension}"
    await put_object(storage_key, data)
    asset = Asset(
        id=asset_id,
        user_id=user_id,
        kind=kind,
        source=source,
        storage_key=storage_key,
        image_format=meta.image_format,
        width=meta.width,
        height=meta.height,
        size_bytes=len(data),
        has_alpha=meta.has_alpha,
    )
    session.add(asset)
    await session.commit()
    return asset


async def list_for_user(session: AsyncSession, user_id: uuid.UUID, limit: int) -> list[Asset]:
    result = await session.execute(
        select(Asset)
        .where(Asset.user_id == user_id)
        .order_by(Asset.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def get_for_user(
    session: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset | None:
    """id + user_id 联合条件单一入口：未命中 None，路由翻 404 不泄露存在性。"""
    result = await session.execute(
        select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id)
    )
    return result.scalar_one_or_none()
