"""ARQ 队列原语：连接池惰性创建，应用关闭时释放。

enqueue 以 run id 作为 job id——重复投递同一 run 不会二次执行，
幂等落在队列的去重键上，不自建"先查再投"的防重查询。
"""
import uuid

from arq import ArqRedis
from arq.connections import RedisSettings

from app.config import get_settings

# 与 events.REDIS_TIMEOUT_SECONDS 同口径：半开连接（wslrelay 残留监听）下
# enqueue 必须秒级失败为 RedisError（路由翻 503），不能悬挂。
# 不用 create_pool：它在创建时 ping，半开连接下这个 ping 先悬挂。
REDIS_TIMEOUT_SECONDS = 3.0

_pool: ArqRedis | None = None


async def _get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        settings = RedisSettings.from_dsn(get_settings().redis_url)
        _pool = ArqRedis(
            host=settings.host,
            port=settings.port,
            db=settings.database,
            username=settings.username or None,
            password=settings.password or None,
            ssl=settings.ssl,
            socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
            socket_timeout=REDIS_TIMEOUT_SECONDS,
        )
    return _pool


async def enqueue(task: str, run_id: uuid.UUID) -> None:
    """投递任务；job id = run id（幂等键）。"""
    pool = await _get_pool()
    await pool.enqueue_job(task, str(run_id), _job_id=str(run_id))


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
