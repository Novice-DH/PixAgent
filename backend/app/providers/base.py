"""Provider 协议与异常：模型平台的一等抽象边界。

GenerateRequest 只传原始字节——参考图的编码方式（base64 内联 / 临时 URL）
由各 Provider 自决，这是协议边界；失败一律抛 ProviderError（模型侧明确失败，
原因可透出给用户，与未预期异常的两级消息分界）。
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


class ProviderError(Exception):
    """模型侧明确失败：原因可透出给用户。"""


@dataclass(frozen=True)
class GenerateRequest:
    prompt: str
    width: int
    height: int
    count: int
    negative_prompt: str | None = None
    seed: int | None = None
    references: list[bytes] = field(default_factory=list)


# 进度回调：(progress, stage) 直通 runs.report——单调性由服务端收口
ProgressCallback = Callable[[int, str], Awaitable[None]]


class ImageProvider:
    """协议基类：name 标识 + generate 返回候选图字节列表（PNG）。"""

    name: str

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback
    ) -> list[bytes]:
        raise NotImplementedError
