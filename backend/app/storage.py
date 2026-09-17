"""对象存储原语：boto3 S3 客户端（MinIO 兼容）+ 建桶 + 对象读写 + 签名 URL。

字节在对象存储，数据库只存元数据与存储键。boto3 是同步 SDK——
触碰网络的调用一律经 asyncio.to_thread 包装，避免阻塞事件循环；
signed_url 是纯本地 HMAC 计算，可直接同步调用、每次响应现算、永不落库。
"""
import asyncio
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings

_REGION = "us-east-1"  # MinIO 占位值；s3v4 签名需要显式 region


@lru_cache
def _client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=_REGION,
        # 本地 MinIO 连接应在秒级显形：超时/重试上限让宕机时健康检查与上传 503 快速返回
        config=Config(
            signature_version="s3v4",
            connect_timeout=3,
            read_timeout=10,
            retries={"max_attempts": 2},
        ),
    )


async def ensure_bucket() -> None:
    """head 失败才 create——幂等；应用启动 lifespan 调用。"""

    def _ensure() -> None:
        client = _client()
        try:
            client.head_bucket(Bucket=get_settings().s3_bucket)
        except ClientError:
            client.create_bucket(Bucket=get_settings().s3_bucket)

    await asyncio.to_thread(_ensure)


async def check() -> None:
    """轻量存储探测：健康检查用；失败抛 ClientError，由调用方折叠为 error 字段。"""
    await asyncio.to_thread(_client().head_bucket, Bucket=get_settings().s3_bucket)


async def put_object(key: str, data: bytes) -> None:
    bucket = get_settings().s3_bucket
    await asyncio.to_thread(_client().put_object, Bucket=bucket, Key=key, Body=data)


async def get_object(key: str) -> bytes:
    """后续期次挂点：Worker 读取原图。"""
    bucket = get_settings().s3_bucket
    response = await asyncio.to_thread(_client().get_object, Bucket=bucket, Key=key)
    return await asyncio.to_thread(response["Body"].read)


async def delete_object(key: str) -> None:
    """后续期次挂点：素材删除与孤儿清理。"""
    bucket = get_settings().s3_bucket
    await asyncio.to_thread(_client().delete_object, Bucket=bucket, Key=key)


def signed_url(key: str) -> str:
    """s3v4 预签名 GET，有效期 = S3_URL_TTL；纯本地计算零网络请求。"""
    settings = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_url_ttl,
    )
