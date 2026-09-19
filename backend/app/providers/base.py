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


@dataclass(frozen=True)
class EditRequest:
    """按提示词编辑已有图：width/height 有值时同时改画幅（扩图），缺省保持原画幅。"""

    prompt: str
    image: bytes
    count: int = 1
    width: int | None = None
    height: int | None = None
    negative_prompt: str | None = None


# 进度回调：(progress, stage) 直通 runs.report——单调性由服务端收口
ProgressCallback = Callable[[int, str], Awaitable[None]]


class ImageProvider:
    """协议基类：name + 三方法（generate/edit/upscale），失败一律抛 ProviderError。

    generate 返回候选图字节列表（PNG）；edit 按提示词改已有图；upscale 提高
    分辨率不改变构图。新增平台必须三方法齐活——协议按业务能力定义，实现按
    可用性组合（upscale 可以用 edit 通道实现，调用方不感知）。
    """

    name: str

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback
    ) -> list[bytes]:
        raise NotImplementedError

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback
    ) -> list[bytes]:
        raise NotImplementedError

    async def upscale(
        self, image: bytes, scale: int, on_progress: ProgressCallback
    ) -> bytes:
        raise NotImplementedError
