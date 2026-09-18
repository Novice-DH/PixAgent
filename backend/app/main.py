"""FastAPI 应用组装：/api 总前缀 + SSE 独立前缀 + 生产态条件托管前端产物 + 启停清理。

同源是架构主轴：不引入任何 CORS 中间件，跨端传输由 Vite proxy（开发态）
与静态托管（生产态）解决。SSE 挂 /events（不挂 /api）：反代可按路径单独关闭缓冲。
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import queue
from app.config import get_settings
from app.events import close_redis
from app.routers import assets, auth, events, health, runs
from app.storage import ensure_bucket

settings = get_settings()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 建桶尽力而为：存储启动失败不阻断 API——健康检查报告 storage 降级，
    # MinIO 恢复后桶早已持久化（数据卷不随容器重启丢失）
    try:
        await ensure_bucket()
    except Exception:
        logger.warning("启动时 MinIO 建桶失败，storage 以降级状态运行", exc_info=True)
    yield
    await queue.close_queue()
    await close_redis()


app = FastAPI(
    title="AI 修图智能体",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(auth.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(health.router, prefix="/api")
# SSE 不挂 /api 前缀
app.include_router(events.router, prefix="/events")

# 生产态：前端构建产物存在时由后端同源托管（开发态目录不存在，跳过）
if settings.frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
