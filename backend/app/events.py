"""Redis Pub/Sub 封装：进度事件的发布与订阅原语。

runs 服务每次状态落库后立即 publish snapshot；SSE 端点先 subscribe 再读快照
（时序铁律：顺序反了会漏掉两步之间发生的终态）。频道约定 run:{run_id}。
"""
import json
import uuid
from functools import cache
from typing import Any

from redis.asyncio import Redis

from app.config import get_settings

# SSE 空闲心跳：15 秒无消息发 ping 注释帧，防代理掐闲连接
IDLE_HEARTBEAT_SECONDS = 15.0
# Redis 命令超时：半开连接（如 Windows Docker Desktop 停容器后 wslrelay 残留监听）
# 会让无超时的命令永久悬挂——故障必须在秒级显形。发布失败由 runs._publish 捕获，
# 订阅侧 get_message 用显式 timeout 参数，不受此默认值影响。
REDIS_TIMEOUT_SECONDS = 3.0


@cache
def redis_client() -> Redis:
    """共享 Redis 客户端唯一入口：Pub/Sub 与选区存储共用同一连接生命周期。"""
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
    )


def channel_for(run_id: uuid.UUID) -> str:
    return f"run:{run_id}"


async def publish_snapshot(run_id: uuid.UUID, snapshot: dict[str, Any]) -> None:
    """状态每次落库后立即广播；负载即 SSE 帧 payload（JSON、非 ASCII 原样）。"""
    await redis_client().publish(channel_for(run_id), json.dumps(snapshot, ensure_ascii=False))


class RunSubscription:
    """一条 SSE 连接的 Pub/Sub 订阅句柄。

    next_snapshot 超时返回 None，由调用方发心跳；订阅必须先于读快照发生。
    """

    def __init__(self, run_id: uuid.UUID) -> None:
        self._run_id = run_id
        self._pubsub = redis_client().pubsub()

    async def subscribe(self) -> None:
        await self._pubsub.subscribe(channel_for(self._run_id))

    async def next_snapshot(
        self, timeout: float = IDLE_HEARTBEAT_SECONDS
    ) -> dict[str, Any] | None:
        message = await self._pubsub.get_message(
            ignore_subscribe_messages=True, timeout=timeout
        )
        if message is None:
            return None
        return json.loads(message["data"])

    async def aclose(self) -> None:
        await self._pubsub.aclose()


async def close_redis() -> None:
    """应用关闭时释放共享连接（lifespan 调用）。"""
    await redis_client().aclose()
    redis_client.cache_clear()
