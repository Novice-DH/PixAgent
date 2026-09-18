"""认证测试夹具：ASGITransport 内存直连、随机凭据、每条测试后按命名空间前缀清理。

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
from app.storage import ensure_bucket

# 测试与手工验证/e2e 脚本共用同一开发库：清理只允许触碰 test_ 命名空间，
# 命名空间外的账号（手工注册、e2e_gen 持久账号）不是测试数据，禁止删除。
TEST_USER_PREFIX = "test_"
TEST_PASSWORD = "test-password-123"


@pytest.fixture(scope="session", autouse=True)
async def _ensure_bucket():
    """与生产 lifespan 同一路径：session 级保证 bucket 存在（幂等）。"""
    await ensure_bucket()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
def credentials() -> dict[str, str]:
    """用户名固定前缀 + 随机串（隔离并行/重跑），密码固定值。"""
    return {"username": f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:12]}", "password": TEST_PASSWORD}


@pytest.fixture(autouse=True)
async def _clean_users_table():
    yield
    async with SessionFactory() as session:
        # autoescape=True：转义前缀中的 _ 通配符，只匹配字面 "test_" 开头的行，
        # 避免误伤 tester 等以 test 开头但不属测试命名空间的账号。
        await session.execute(
            delete(User).where(User.username.startswith(TEST_USER_PREFIX, autoescape=True))
        )
        await session.commit()
