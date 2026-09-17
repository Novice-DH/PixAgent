"""认证测试夹具：ASGITransport 内存直连、随机凭据、每条测试后清表。

数据库引擎在模块级创建（app.db.engine），配合 pyproject 的
session 级事件循环两项配置，连接不跨事件循环复用。
"""
import uuid

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete

from app.db import SessionFactory
from app.main import app
from app.models.user import User

TEST_PASSWORD = "test-password-123"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
def credentials() -> dict[str, str]:
    """用户名固定前缀 + 随机串（隔离并行/重跑），密码固定值。"""
    return {"username": f"u_{uuid.uuid4().hex[:12]}", "password": TEST_PASSWORD}


@pytest.fixture(autouse=True)
async def _clean_users_table():
    yield
    async with SessionFactory() as session:
        await session.execute(delete(User))
        await session.commit()
