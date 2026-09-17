"""健康端点行为测试：ASGITransport 内存直连 app，不起真实服务器，但依赖真实 PostgreSQL。"""
import httpx
from httpx import ASGITransport

from app.main import app


async def test_health_ok_when_database_reachable() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {"api": "ok", "database": "ok"}


async def test_openapi_served_under_api_prefix() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "AI 修图智能体"
