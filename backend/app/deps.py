"""请求级依赖：统一鉴权入口。

认证链（Cookie 缺失 → 签名/过期 → 用户存在）任何一环失败都坍缩为
同一条 401「未登录或会话已过期」——报错越精细越容易被枚举利用。
"""
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.db import SessionDep
from app.models.user import User
from app.security import SESSION_COOKIE, parse_session_token
from app.services.auth import get_by_id

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="未登录或会话已过期",
)


async def current_user(
    session: SessionDep,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    user_id = parse_session_token(session_token) if session_token else None
    user = await get_by_id(session, user_id) if user_id is not None else None
    if user is None:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(current_user)]
