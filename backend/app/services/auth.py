"""认证服务：注册 / 登录 / 按 id 查询。

业务规则层：抛领域异常、管事务，不 import fastapi——
认证规则可脱离 HTTP 独立测试，Worker 内复用不受阻。
用户名占用的权威判定是数据库唯一索引（IntegrityError → rollback）；
用户不存在与密码错误坍缩为同一个 InvalidCredentials，防枚举。
"""
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security import hash_password, verify_password


class UsernameTaken(Exception):
    """用户名已被占用。"""


class InvalidCredentials(Exception):
    """用户名或密码错误。"""


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def register(session: AsyncSession, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise UsernameTaken(username) from None
    return user


async def authenticate(session: AsyncSession, username: str, password: str) -> User:
    user = await get_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials
    return user
