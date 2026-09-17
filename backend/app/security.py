"""安全原语：会话 Cookie 常量、bcrypt 密码哈希与 JWT 签发/解析。

密码学与令牌的唯一入口；解析对一切失败（过期/签名错/格式错/sub 非法）
统一返回"未认证"，不区分原因——客户端的处理方式只有重新登录一种。
"""
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

SESSION_COOKIE = "session"
_JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # 哈希格式损坏按"密码不匹配"处理，不让脏数据炸成 500
        return False


def create_session_token(user_id: uuid.UUID, ttl_hours: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "exp": now + timedelta(hours=ttl_hours)}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_JWT_ALGORITHM)


def parse_session_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
