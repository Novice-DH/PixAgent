# ===== stage 1：前端构建 =====
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ===== stage 2：Python 运行时 + uv + 前端产物 =====
# 多阶段单镜像；启动命令由 compose 提供（api/worker 两种进程），镜像内不写 CMD
FROM python:3.13-slim
# 构建期可用 --build-arg UV_DEFAULT_INDEX=<镜像源> 适配受限网络；默认官方源
ARG UV_DEFAULT_INDEX=https://pypi.org/simple
ENV UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX}
RUN pip install --no-cache-dir uv

ENV UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:${PATH}"

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
