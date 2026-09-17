"""generate_images 任务包装：终态短路 + 兜底落败。

worker 重启后 ARQ 重投未确认任务是常态而非异常——第一件事查终态，
把"重复消费不二次调用模型（真实平台即二次扣费）"变成最显眼的一行。
"""
import logging
import uuid

from app.db import SessionFactory
from app.services import generation, runs

logger = logging.getLogger(__name__)


async def generate_images(ctx: dict, run_id: str) -> None:
    """ARQ 任务入口；job id = run id，重复投递天然幂等。"""
    async with SessionFactory() as session:
        run = await runs.load(session, uuid.UUID(run_id))
        if run is None:
            logger.warning("任务对应的 run 不存在，跳过 run_id=%s", run_id)
            return
        if run.status.is_terminal:
            # 终态短路：队列重投或 worker 重启的重复消费到此为止
            return
        try:
            await generation.execute(session, run)
        except Exception:
            # 兜底：execute 内部已两级分类，走到这里说明分类过程本身故障（如终态落库失败）。
            # 订阅进度的客户端不能空等——rollback 后补一帧 FAILED 终态。
            logger.exception("generate_images 兜底落败 run_id=%s", run_id)
            await session.rollback()
            fresh = await runs.load(session, run.id)
            if fresh is not None and not fresh.status.is_terminal:
                await runs.finish_failed(session, fresh, generation.UNEXPECTED_FAILURE_MESSAGE)
