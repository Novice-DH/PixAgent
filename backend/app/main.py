"""FastAPI 应用组装：/api 总前缀 + 生产态条件托管前端产物。

同源是架构主轴：不引入任何 CORS 中间件，跨端传输由 Vite proxy（开发态）
与静态托管（生产态）解决。
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import auth, health

settings = get_settings()

app = FastAPI(
    title="AI 修图智能体",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(auth.router, prefix="/api")
app.include_router(health.router, prefix="/api")

# 生产态：前端构建产物存在时由后端同源托管（开发态目录不存在，跳过）
if settings.frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
