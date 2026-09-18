"""ARQ 队列原语：连接池惰性创建，应用关闭时释放。

enqueue 以 run id 作为 job id——重复投递同一 run 不会二次执行，
幂等落在队列的去重键上，不自建"先查再投"的防重查询。
"""
import uuid

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None


async def _get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
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
