"""素材端点行为测试：八条契约行为 + probe 纯函数单测。

图片一律用 PIL 在内存中现做真实字节，不依赖 fixture 文件；
图片字节经 MinIO 真实读写（bucket 由 session 夹具保证存在）。
"""
import struct
from io import BytesIO

from PIL import Image
from sqlalchemy import func, select

from app.db import SessionFactory
from app.models.asset import Asset
from app.models.user import User
from app.services.images import ImageRejected, probe

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_bytes(size: tuple[int, int] = (64, 48), mode: str = "RGB") -> bytes:
    img = Image.new(mode, size, (255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(size: tuple[int, int] = (64, 48)) -> bytes:
    img = Image.new("RGB", size, (10, 200, 10))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _gif_bytes() -> bytes:
    img = Image.new("RGB", (64, 48), (0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


async def _register_and_get_client(client, username: str) -> None:
    response = await client.post(
        "/api/auth/register", json={"username": username, "password": "test-password-123"}
    )
    assert response.status_code == 201


async def _upload(
    client, data: bytes, filename: str = "upload.png", content_type: str = "image/png"
):
    return await client.post(
        "/api/assets",
        files={"file": (filename, data, content_type)},
    )


async def test_upload_returns_metadata_and_signed_url(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    data = _png_bytes((320, 240))

    response = await _upload(client, data)

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "original"
    assert body["source"] == "upload"
    assert body["image_format"] == "PNG"
    assert body["width"] == 320
    assert body["height"] == 240
    assert body["size_bytes"] == len(data)
    assert body["has_alpha"] is False
    assert "localhost:7313" in body["url"]
    assert "X-Amz-Signature" in body["url"]  # s3v4 预签名

    # 元数据落库、字节不入库：本测试用户的素材恰好一条（过滤共享库中的其他数据）
    async with SessionFactory() as session:
        user_id = await session.scalar(
            select(User.id).where(User.username == credentials["username"])
        )
        count = (
            await session.execute(
                select(func.count()).select_from(Asset).where(Asset.user_id == user_id)
            )
        ).scalar_one()
    assert count == 1


async def test_alpha_channel_detection(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])

    alpha_response = await _upload(client, _png_bytes((64, 48), mode="RGBA"))
    opaque_response = await _upload(client, _jpeg_bytes())

    assert alpha_response.json()["has_alpha"] is True
    assert opaque_response.json()["has_alpha"] is False


async def test_corrupted_file_returns_422(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])

    response = await _upload(client, PNG_SIGNATURE + b"this-is-not-really-png-data")

    assert response.status_code == 422
    assert response.json()["detail"] == "文件已损坏或不是受支持的图片"


async def test_gif_returns_422(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])

    response = await _upload(
        client, _gif_bytes(), filename="animated.gif", content_type="image/gif"
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "文件已损坏或不是受支持的图片"


async def test_disguised_extension_recorded_by_decoding(client, credentials) -> None:
    """JPEG 字节伪装 .png 扩展名 + text/plain Content-Type：按解码结果 JPEG 记录。"""
    await _register_and_get_client(client, credentials["username"])

    response = await _upload(client, _jpeg_bytes(), filename="fake.png", content_type="image/png")

    assert response.status_code == 201
    body = response.json()
    assert body["image_format"] == "JPEG"
    assert body["has_alpha"] is False


async def test_upload_requires_authentication(client) -> None:
    response = await _upload(client, _png_bytes())

    assert response.status_code == 401
    assert response.json()["detail"] == "未登录或会话已过期"


async def test_cross_user_isolation_returns_404_and_empty_list(
    client, credentials, other_credentials
) -> None:
    await _register_and_get_client(client, credentials["username"])
    upload = await _upload(client, _png_bytes())
    asset_id = upload.json()["id"]

    await _register_and_get_client(client, other_credentials["username"])

    forbidden = await client.get(f"/api/assets/{asset_id}")
    assert forbidden.status_code == 404
    assert forbidden.json()["detail"] == "素材不存在"

    listing = await client.get("/api/assets")
    assert listing.status_code == 200
    assert listing.json() == []


async def test_tiny_image_rejected(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])

    response = await _upload(client, _png_bytes((16, 16)))

    assert response.status_code == 422
    assert response.json()["detail"] == "文件已损坏或不是受支持的图片"


# ---- probe 纯函数直接单测 ----


def test_probe_rejects_empty_and_garbage() -> None:
    for bad in (b"", PNG_SIGNATURE + b"garbage"):
        try:
            probe(bad)
        except ImageRejected:
            pass
        else:
            raise AssertionError(f"{bad[:8]!r} 应被拒绝")


def test_probe_rejects_decompression_bomb_header() -> None:
    """伪造 IHDR 声明 20000×20000（≈4 亿像素）的仅头部 PNG：open 阶段防炸弹异常 → 422 而非 500。"""
    ihdr = struct.pack(">II", 20000, 20000) + b"\x08\x06\x00\x00\x00"
    bomb = (
        PNG_SIGNATURE
        + b"\x00\x00\x00\rIHDR" + ihdr
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    try:
        probe(bomb)
    except ImageRejected:
        pass
    else:
        raise AssertionError("解压炸弹头部应被拒绝")


def test_probe_meta_and_extension_mapping() -> None:
    meta = probe(_png_bytes((100, 50)))
    assert (meta.image_format, meta.width, meta.height, meta.has_alpha) == ("PNG", 100, 50, False)
    assert meta.extension == "png"

    jpeg_meta = probe(_jpeg_bytes())
    assert jpeg_meta.image_format == "JPEG"
    assert jpeg_meta.extension == "jpg"
