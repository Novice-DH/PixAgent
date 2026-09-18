"""mock Provider：本地占位图，零费用、可复现——构图由 prompt 的 SHA-256 哈希决定。

同一提示词永远同一输出：测试与 e2e 断言可精确到尺寸与张数，不用摸彩票。
进度锚点（逐张回调）与真实 Provider 的节奏对齐，切换 Provider 时前端无感。
"""
import asyncio
import hashlib
from io import BytesIO

from PIL import Image, ImageDraw

from app.providers.base import GenerateRequest, ProgressCallback

# 每张间隔（秒）：模拟真实生图节奏，让 SSE 进度可观察
PER_IMAGE_DELAY_SECONDS = 0.4


class MockImageProvider:
    name = "mock"

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback
    ) -> list[bytes]:
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
        images: list[bytes] = []
        for index in range(request.count):
            await on_progress(45, f"生成第 {index + 1} / {request.count} 张")
            images.append(self._render(request, digest, index))
            await asyncio.sleep(PER_IMAGE_DELAY_SECONDS)
        return images

    def _render(self, request: GenerateRequest, digest: str, index: int) -> bytes:
        """确定性绘制：从哈希派生调色板与几何布局，纯装饰构图、不含文字。"""
        seed_material = hashlib.sha256(f"{digest}:{index}".encode()).hexdigest()

        def take(tag: int) -> int:
            # 按 tag 派生 32 位伪随机数：不限次数、同输入同输出
            segment = hashlib.sha256(f"{seed_material}:{tag}".encode()).hexdigest()
            return int(segment[:8], 16)

        base_hue = take(0) % 360
        bands = 5 + take(1) % 4
        circles = 3 + take(2) % 4

        img = Image.new("RGB", (request.width, request.height), "#f5f4f0")
        draw = ImageDraw.Draw(img, "RGBA")

        # 色带：低饱和同色调渐变
        for band in range(bands):
            hue = (base_hue + band * 14) % 360
            top = request.height * band // bands
            bottom = request.height * (band + 1) // bands
            draw.rectangle(
                [0, top, request.width, bottom],
                fill=(hue % 256, 120 + (hue * 7) % 100, 160 + (hue * 3) % 80, 90),
            )

        # 圆形：错落装饰
        for circle in range(circles):
            cx = take(10 + circle) % request.width
            cy = take(20 + circle) % request.height
            radius = 40 + take(30 + circle) % (min(request.width, request.height) // 4)
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=((base_hue * circle) % 256, 140, 170, 70),
                outline=((base_hue * circle) % 256, 90, 120, 160),
                width=6,
            )

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
