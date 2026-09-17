"""链路验证任务。"""


async def ping(ctx: dict) -> str:
    """用于验证 API 到 worker 的投递链路是否连通。"""
    return "pong"
