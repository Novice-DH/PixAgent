"""认证路由：协议与状态码翻译，业务规则在服务层。

注册即建会话（201 同时 Set-Cookie），不做"注册成功 → 再调登录"两步走。
"""
import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.config import get_settings
from app.db import SessionDep
from app.deps import CurrentUser
from app.schemas.auth import Credentials, UserOut
from app.security import SESSION_COOKIE, create_session_token
from app.services.auth import InvalidCredentials, UsernameTaken, authenticate, register

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user_id: uuid.UUID) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(user_id, settings.jwt_ttl_hours),
        max_age=settings.jwt_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    credentials: Credentials, response: Response, session: SessionDep
) -> UserOut:
    try:
        user = await register(session, credentials.username, credentials.password)
    except UsernameTaken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="该用户名已被占用"
        ) from None
    _set_session_cookie(response, user.id)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
async def login_user(credentials: Credentials, response: Response, session: SessionDep) -> UserOut:
    try:
        user = await authenticate(session, credentials.username, credentials.password)
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        ) from None
    _set_session_cookie(response, user.id)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(response: Response) -> None:
    # 无状态 JWT：logout 只清 Cookie，不吊销令牌
    response.delete_cookie(key=SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
async def read_authenticated_user(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
