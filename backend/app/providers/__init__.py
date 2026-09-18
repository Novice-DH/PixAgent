"""Provider 登记表：IMAGE_PROVIDER 配置 → 实现实例。

新增平台只在 _REGISTRY 加一行；未知值在启动首次调用时即抛错显形。
"""
from collections.abc import Callable
from functools import lru_cache

from app.config import get_settings
from app.providers.base import GenerateRequest, ImageProvider, ProgressCallback, ProviderError
from app.providers.dashscope import DashscopeImageProvider
from app.providers.mock import MockImageProvider

_REGISTRY: dict[str, Callable[[], ImageProvider]] = {
    "mock": MockImageProvider,
    "dashscope": DashscopeImageProvider,
}


@lru_cache
def get_image_provider() -> ImageProvider:
    name = get_settings().image_provider
    factory = _REGISTRY.get(name)
    if factory is None:
        raise ProviderError(f"未知的 IMAGE_PROVIDER：{name}")
    return factory()


__all__ = [
    "GenerateRequest",
    "ImageProvider",
    "ProgressCallback",
    "ProviderError",
    "get_image_provider",
]
