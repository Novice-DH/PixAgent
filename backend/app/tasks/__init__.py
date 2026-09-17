"""异步任务注册表：Worker 的函数表从这里导入。

新增任务后在此登记，API 侧即可经 Redis 队列投递。
"""

from collections.abc import Awaitable, Callable

from app.tasks.ping import ping

TASKS: dict[str, Callable[..., Awaitable[object]]] = {
    "ping": ping,
}
