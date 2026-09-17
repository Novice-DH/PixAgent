"""健康端点行为测试：三键契约（api/database/storage），ASGITransport 内存直连。"""
import httpx
from httpx import ASGITransport

from app.main import app


async def test_health_ok_when_dependencies_reachable() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {"api": "ok", "database": "ok", "storage": "ok"}


async def test_health_reports_dependency_errors_without_crashing() -> None:
    """依赖故障折叠为 error: <类名>，HTTP 仍 200——停 MinIO 场景的进程内等价验证。"""
    from unittest.mock import patch

    from botocore.exceptions import ClientError

    transport = ASGITransport(app=app)
    with patch("app.routers.health.check_storage", side_effect=ClientError({}, "HeadBucket")):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "ok"
    assert body["database"] == "ok"
    assert body["storage"] == "error: ClientError"


async def test_openapi_served_under_api_prefix() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "AI 修图智能体"
