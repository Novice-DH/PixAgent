"""mock Provider：本地占位图，零费用、可复现——构图由 prompt 的 SHA-256 哈希决定。

同一提示词永远同一输出：测试与 e2e 断言可精确到尺寸与张数，不用摸彩票。
进度锚点（逐张回调）与真实 Provider 的节奏对齐，切换 Provider 时前端无感。
编辑（edit）的换背景/扩图两种形态由目标尺寸区分：同尺寸主体缩 0.88 露新底，
异尺寸原大居中——端到端断言只看尺寸与张数，不需要两个 mock。
"""
import asyncio
import colorsys
import hashlib
from io import BytesIO

from PIL import Image, ImageDraw

from app.providers.base import EditRequest, GenerateRequest, ProgressCallback

# 每张间隔（秒）：模拟真实生图节奏，让 SSE 进度可观察
PER_IMAGE_DELAY_SECONDS = 0.4


def _png(image: Image.Image) -> bytes:
    """统一 PNG 输出：generate 与 edit/upscale 共用同一编码路径。"""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


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

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback
    ) -> list[bytes]:
        subject = Image.open(BytesIO(request.image)).convert("RGBA")
        target = (
            (request.width, request.height)
            if request.width is not None and request.height is not None
            else subject.size
        )
        base_seed = int(hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:8], 16)
        images: list[bytes] = []
        for index in range(request.count):
            await on_progress(
                int((index + 1) / request.count * 100),
                f"生成第 {index + 1} / {request.count} 张",
            )
            images.append(self._compose(subject, target, base_seed + index * 977, request.prompt))
            await asyncio.sleep(PER_IMAGE_DELAY_SECONDS)
        return images

    async def upscale(self, image: bytes, scale: int, on_progress: ProgressCallback) -> bytes:
        subject = Image.open(BytesIO(image)).convert("RGBA")
        await on_progress(40, "放大画幅")
        await asyncio.sleep(PER_IMAGE_DELAY_SECONDS)
        resized = subject.resize(
            (subject.width * scale, subject.height * scale), Image.LANCZOS
        )
        await on_progress(90, "保存结果")
        return _png(resized)

    def _compose(
        self, subject: Image.Image, target: tuple[int, int], seed: int, prompt: str
    ) -> bytes:
        """确定性合成：色相由 seed 决定的底色画布 + 主体居中（形态由尺寸关系决定）。"""
        hue = (seed % 360) / 360.0
        rgb = colorsys.hsv_to_rgb(hue, 0.45, 0.92)
        canvas = Image.new("RGBA", target, tuple(int(channel * 255) for channel in (*rgb, 1.0)))

        if target == subject.size:
            # 换背景形态：主体缩 0.88 居中，露出新底
            inner = subject.resize(
                (int(subject.width * 0.88), int(subject.height * 0.88)), Image.LANCZOS
            )
        else:
            # 扩图形态：主体原大居中
            inner = subject
        offset = ((target[0] - inner.width) // 2, (target[1] - inner.height) // 2)
        canvas.alpha_composite(inner, offset)

        draw = ImageDraw.Draw(canvas)
        draw.text((8, 8), prompt[:40], fill=(255, 255, 255, 230))
        return _png(canvas)

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

        return _png(img)
