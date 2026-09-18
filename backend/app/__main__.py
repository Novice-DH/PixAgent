"""本地开发启动入口：`python -m app`（backend/ 目录下执行，通常经 `uv run` 包装）。

端口唯一来源是 `.env` 的 `API_PORT`（Settings.api_port）；容器部署的启动命令
单点在 compose 显式 command，本地入口单点在此——两套入口各管一个环境，不混用。
"""
import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("app.main:app", host="127.0.0.1", port=settings.api_port)


if __name__ == "__main__":
    main()
