"""arq Worker 进程入口：`arq app.worker.WorkerSettings`。

与 uvicorn 是两个进程、一个镜像，经 Redis 队列解耦耗时任务；
参数为本项目长期约定，不随部署环境变化。
"""
from arq.connections import RedisSettings

from app.config import get_settings
from app.tasks import TASKS

settings = get_settings()


class WorkerSettings:
    functions: list = list(TASKS.values())
    redis_settings: RedisSettings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300
    keep_result = 3600
