"""测试基础设施夹具单点：内存直连、双向隔离硬化、随机凭据、命名空间清理。

硬化三条全部 session 级 autouse（绕不开的入口）：
- mock_provider：测试期间强制 mock Provider——本机 .env 漂移（如 IMAGE_PROVIDER=dashscope）
  不能让测试产生真实调用费用；
- isolated_redis：Redis 指到 1 号库——开发中的 worker 只监听默认库，
  抢不走测试受理的任务；
- other_credentials：第二账号凭据统一入口，跨用户用例不再各文件手写。

数据库引擎在模块级创建（app.db.engine），配合 pyproject 的
session 级事件循环两项配置，连接不跨事件循环复用。
"""
import uuid

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete

from app import events, queue
from app.config import get_settings
from app.db import SessionFactory
from app.main import app
from app.models.user import User
from app.providers import get_image_provider
from app.storage import ensure_bucket

# 测试与手工验证/e2e 脚本共用同一开发库：清理只允许触碰 test_ 命名空间，
# 命名空间外的账号（手工注册、e2e_gen 持久账号）不是测试数据，禁止删除。
TEST_USER_PREFIX = "test_"
TEST_PASSWORD = "test-password-123"


def _isolate_redis_url(url: str) -> str:
    """原 url 末段是数字（已有库号）则替换为 1，否则追加 /1。"""
    head, _, tail = url.rpartition("/")
    return f"{head}/1" if tail.isdigit() else f"{url}/1"


@pytest.fixture(scope="session", autouse=True)
def mock_provider():
    """测试期间强制 image_provider=mock 并清 Provider 登记处缓存，结束还原再清。"""
    settings = get_settings()
    original = settings.image_provider
    settings.image_provider = "mock"
    get_image_provider.cache_clear()
    yield
    settings.image_provider = original
    get_image_provider.cache_clear()


@pytest.fixture(scope="session", autouse=True)
async def isolated_redis():
    """测试期间 redis_url 指到 1 号库；teardown 关连接、还原配置、再清缓存。

    events 的共享连接与 queue 的连接池各自持有缓存，改配置后必须清掉，
    否则旧连接（默认库）仍在被复用——隔离就成了摆设。
    """
    settings = get_settings()
    original = settings.redis_url
    settings.redis_url = _isolate_redis_url(original)
    events._redis.cache_clear()
    await queue.close_queue()
    yield
    await events.close_redis()
    await queue.close_queue()
    settings.redis_url = original
    events._redis.cache_clear()


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


@pytest.fixture
def other_credentials() -> dict[str, str]:
    """第二账号凭据：生成规则与 credentials 完全一致（跨用户用例统一入口）。"""
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
