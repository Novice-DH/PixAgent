"""dashscope（阿里云百炼）文生图 Provider：异步任务接口，就位不启用（无 key 不生效）。

生命周期：提交（X-DashScope-Async: enable）→ task_id → 3 秒轮询 → 300 秒超时；
结果 URL 有效期 24 小时——取回终态后立即下载字节返回（转存自有对象存储由
生成服务统一完成，对外暴露的永远是自己的签名 URL）。
参考图以 base64 data URI 内联：本地 MinIO 的签名 URL 模型服务访问不到。
一切 HTTP/解析错误归一为 ProviderError——两级失败消息的"模型侧明确失败"档。
"""
import asyncio
import base64
import logging

import httpx

from app.config import get_settings
from app.providers.base import GenerateRequest, ProgressCallback, ProviderError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com"
TEXT2IMAGE_PATH = "/api/v1/services/aigc/text2image/image-synthesis"
TASK_PATH = "/api/v1/tasks/{task_id}"

POLL_INTERVAL_SECONDS = 3.0
POLL_TIMEOUT_SECONDS = 300.0
REQUEST_TIMEOUT_SECONDS = 30.0

# DashScope 任务状态 → 进度锚点（与 mock 的回调节奏对齐，切换 Provider 前端无感）
_STATUS_PROGRESS = {"PENDING": (10, "排队中"), "RUNNING": (45, "生成中")}
_TERMINAL_TASK_STATUS = {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}


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

    async def _submit(self, client: httpx.AsyncClient, payload: dict) -> str:
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
