"""dashscope（阿里云百炼）Provider：文生图走异步任务接口，图片编辑走同步端点。

两条路径的分界是端点能力而非偏好：文生图提交带 X-DashScope-Async（task_id →
3 秒轮询 → 300 秒超时）；多模态编辑端点不支持异步任务头，同步等待单请求
180 秒——这只发生在 Worker 侧的 httpx 调用里（job_timeout=300 兜底），API
进程永远不直接调它。结果 URL 有效期 24 小时——取回终态后立即下载字节返回
（转存自有对象存储由生成服务统一完成，对外暴露的永远是自己的签名 URL）。
参考图与原图以 base64 data URI 内联：本地 MinIO 的签名 URL 模型服务访问不到。
一切 HTTP/解析错误归一为 ProviderError——两级失败消息的"模型侧明确失败"档。
"""
import asyncio
import base64
import logging
from io import BytesIO

import httpx
from PIL import Image

from app.config import get_settings
from app.providers.base import EditRequest, GenerateRequest, ProgressCallback, ProviderError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com"
TEXT2IMAGE_PATH = "/api/v1/services/aigc/text2image/image-synthesis"
TASK_PATH = "/api/v1/tasks/{task_id}"
_EDIT_PATH = "/api/v1/services/aigc/multimodal-generation/generation"

POLL_INTERVAL_SECONDS = 3.0
POLL_TIMEOUT_SECONDS = 300.0
REQUEST_TIMEOUT_SECONDS = 30.0
# 编辑端点同步等待：单请求 180 秒，只存在于 Worker 的 httpx 调用（job_timeout=300 兜底）
_EDIT_TIMEOUT = 180.0

# 超分的固定约束提示词：美学契约是"像素更多，内容不变"——防模型自由发挥改变构图
_UPSCALE_PROMPT = "提高清晰度，保持主体、构图和颜色不变，不要添加新元素。"

# DashScope 任务状态 → 进度锚点（与 mock 的回调节奏对齐，切换 Provider 前端无感）
_STATUS_PROGRESS = {"PENDING": (10, "排队中"), "RUNNING": (45, "生成中")}
_TERMINAL_TASK_STATUS = {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}


def _fit_edit_size(width: int, height: int) -> tuple[int, int]:
    """编辑接口边长硬约束 [512, 2048] 的确定性满足：先把短边不足 512 的等比抬到
    512，再把长边超 2048 的等比压回，两步各自取整，最终各边 max(512)——顺序
    不可颠倒，颠倒会先把小图裁变形再抬高。整数运算：抬后短边恰为 512、压后长边恰为 2048。
    """
    if min(width, height) < 512:
        shortest = min(width, height)
        width, height = width * 512 // shortest, height * 512 // shortest
    if max(width, height) > 2048:
        longest = max(width, height)
        width, height = width * 2048 // longest, height * 2048 // longest
    return max(width, 512), max(height, 512)


def _extract_edit_urls(body: dict | None) -> list[str]:
    """同步编辑响应的图片 URL 容错提取：主形态 choices[].message.content[].image，
    兼容 results[].url 形态；两种形态都取不到视为解析失败（调用方抛 ProviderError）。"""
    output = (body or {}).get("output") or {}
    urls: list[str] = []
    for choice in output.get("choices") or []:
        content = ((choice or {}).get("message") or {}).get("content") or []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("image"), str) and item["image"]:
                urls.append(item["image"])
    if not urls:
        for result in output.get("results") or []:
            url = (result or {}).get("url") or (result or {}).get("image")
            if isinstance(url, str) and url:
                urls.append(url)
    return urls


class DashscopeImageProvider:
    name = "dashscope"

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback
    ) -> list[bytes]:
        settings = get_settings()
        if not settings.dashscope_api_key:
            raise ProviderError("未配置模型服务密钥（DASHSCOPE_API_KEY），无法发起生成")

        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "X-DashScope-Async": "enable",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.text_to_image_model,
            "input": {
                "prompt": request.prompt,
                **({"negative_prompt": request.negative_prompt} if request.negative_prompt else {}),
                **(
                    {
                        "ref_imgs": [
                            base64.b64encode(image).decode("ascii") for image in request.references
                        ]
                    }
                    if request.references
                    else {}
                ),
            },
            "parameters": {
                "size": f"{request.width}*{request.height}",
                "n": request.count,
                **({"seed": request.seed} if request.seed is not None else {}),
            },
        }

        async with httpx.AsyncClient(
            base_url=settings.dashscope_base_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            task_id = await self._submit(client, payload)
            result_urls = await self._poll(client, task_id, on_progress)
            return await self._download(client, result_urls)

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback
    ) -> list[bytes]:
        """多模态编辑：同步等待（不带 X-DashScope-Async），不造轮询。"""
        settings = get_settings()
        if not settings.dashscope_api_key:
            raise ProviderError("未配置模型服务密钥（DASHSCOPE_API_KEY），无法发起编辑")

        parameters: dict = {"n": request.count, "watermark": False}
        if request.width is not None and request.height is not None:
            width, height = _fit_edit_size(request.width, request.height)
            parameters["size"] = f"{width}*{height}"
        if request.negative_prompt:
            parameters["negative_prompt"] = request.negative_prompt

        payload = {
            "model": settings.image_edit_model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": "data:image/png;base64,"
                                + base64.b64encode(request.image).decode("ascii")
                            },
                            {"text": request.prompt},
                        ],
                    }
                ]
            },
            "parameters": parameters,
        }

        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(
            base_url=settings.dashscope_base_url,
            headers=headers,
            timeout=_EDIT_TIMEOUT,
        ) as client:
            await on_progress(20, "提交编辑")
            result_urls = await self._edit_urls(client, payload)
            await on_progress(80, "下载结果")
            return await self._download(client, result_urls)

    async def upscale(self, image: bytes, scale: int, on_progress: ProgressCallback) -> bytes:
        """协议层独立、实现层复用 edit：换专用超分模型只改这里，调用方零改动。"""
        with Image.open(BytesIO(image)) as subject:
            width, height = subject.size
        target = _fit_edit_size(width * scale, height * scale)
        results = await self.edit(
            EditRequest(
                prompt=_UPSCALE_PROMPT,
                image=image,
                count=1,
                width=target[0],
                height=target[1],
            ),
            on_progress,
        )
        return results[0]

    async def _edit_urls(self, client: httpx.AsyncClient, payload: dict) -> list[str]:
        body: dict | None = None
        try:
            response = await client.post(_EDIT_PATH, json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException:
            raise ProviderError("模型服务编辑超时，请稍后重试") from None
        except httpx.HTTPError as error:
            raise ProviderError(f"模型服务编辑失败：{error}") from None
        except ValueError:
            logger.warning("dashscope 编辑响应不是合法 JSON")
            raise ProviderError("模型服务返回了无法解析的编辑结果") from None
        result_urls = _extract_edit_urls(body)
        if not result_urls:
            logger.warning("dashscope 编辑响应解析失败：%s", body)
            raise ProviderError("模型服务返回了无法解析的编辑结果")
        return result_urls

    async def _submit(self, client: httpx.AsyncClient, payload: dict) -> str:
        body: dict | None = None
        try:
            response = await client.post(TEXT2IMAGE_PATH, json=payload)
            response.raise_for_status()
            body = response.json()
            task_id = body["output"]["task_id"]
        except httpx.HTTPError as error:
            raise ProviderError(f"模型服务提交失败：{error}") from None
        except (KeyError, TypeError, ValueError):
            logger.warning("dashscope 提交响应解析失败：%s", body)
            raise ProviderError("模型服务返回了无法解析的提交结果") from None
        if not isinstance(task_id, str) or not task_id:
            raise ProviderError("模型服务返回了无效的任务号")
        return task_id

    async def _poll(
        self, client: httpx.AsyncClient, task_id: str, on_progress: ProgressCallback
    ) -> list[str]:
        deadline = asyncio.get_running_loop().time() + POLL_TIMEOUT_SECONDS
        reported: set[str] = set()
        body: dict | None = None
        while True:
            if asyncio.get_running_loop().time() >= deadline:
                raise ProviderError("模型服务任务超时，请稍后重试")
            try:
                response = await client.get(TASK_PATH.format(task_id=task_id))
                response.raise_for_status()
                body = response.json()
                status = body["output"]["task_status"]
            except httpx.HTTPError as error:
                raise ProviderError(f"模型服务查询失败：{error}") from None
            except (KeyError, TypeError, ValueError):
                logger.warning("dashscope 轮询响应解析失败：%s", body)
                raise ProviderError("模型服务返回了无法解析的任务状态") from None

            if status in _TERMINAL_TASK_STATUS:
                if status != "SUCCEEDED":
                    message = body["output"].get("message") or f"任务状态 {status}"
                    raise ProviderError(f"模型服务生成失败：{message}")
                return list(body["output"].get("results", []))

            anchor = _STATUS_PROGRESS.get(status)
            if anchor and status not in reported:
                reported.add(status)
                await on_progress(anchor[0], anchor[1])
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _download(self, client: httpx.AsyncClient, urls: list[str]) -> list[bytes]:
        """临时 URL 立即取回字节——24 小时有效期不能信任给下游。"""
        images: list[bytes] = []
        for url in urls:
            try:
                response = await client.get(url)
                response.raise_for_status()
                images.append(response.content)
            except httpx.HTTPError as error:
                raise ProviderError(f"候选图下载失败：{error}") from None
        return images
