"""认证端点行为测试：覆盖任务书要求的七条行为 + 伪造 cookie 故障注入。

断言依据 specs/account-auth §6.2：状态码与中文消息是硬契约。
"""
from httpx import AsyncClient

SESSION_COOKIE_ATTRIBUTES = {
    "samesite": "lax",
    "httponly": True,
    "path": "/",
}


async def test_register_returns_201_and_sets_session_cookie(
    client: AsyncClient, credentials
) -> None:
    response = await client.post("/api/auth/register", json=credentials)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == credentials["username"]
    assert "id" in body

    cookie_header = response.headers["set-cookie"]
    assert cookie_header.startswith("session=")
    for attribute in ("HttpOnly", "SameSite=lax", "Path=/"):
        assert attribute in cookie_header, f"缺少 Cookie 属性 {attribute}"


async def test_register_duplicate_username_returns_409(client: AsyncClient, credentials) -> None:
    first = await client.post("/api/auth/register", json=credentials)
    assert first.status_code == 201

    duplicate = await client.post("/api/auth/register", json=credentials)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "该用户名已被占用"


async def test_login_then_me_returns_user(client: AsyncClient, credentials) -> None:
    await client.post("/api/auth/register", json=credentials)

    login = await client.post("/api/auth/login", json=credentials)
    assert login.status_code == 200

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body == {"id": login.json()["id"], "username": credentials["username"]}


async def test_login_wrong_password_returns_401(client: AsyncClient, credentials) -> None:
    await client.post("/api/auth/register", json=credentials)

    response = await client.post("/api/auth/login", json={**credentials, "password": "wrong-pass"})

    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


async def test_me_without_session_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "未登录或会话已过期"


async def test_logout_clears_session_then_me_returns_401(client: AsyncClient, credentials) -> None:
    await client.post("/api/auth/register", json=credentials)

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204

    me = await client.get("/api/auth/me")
    assert me.status_code == 401
    assert me.json()["detail"] == "未登录或会话已过期"


async def test_invalid_username_returns_422(client: AsyncClient) -> None:
    for bad_username in ("ab", "has space", "has-symbol", "含中文用户名"):
        response = await client.post(
            "/api/auth/register", json={"username": bad_username, "password": "fine-password"}
        )
        assert response.status_code == 422, f"用户名 {bad_username!r} 应校验失败"


async def test_over_72_bytes_password_returns_422_not_500(client: AsyncClient) -> None:
    """多字节密码可同时满足"6–64 位"却超 bcrypt 72 字节上限，必须 422 而非 500。"""
    response = await client.post(
        "/api/auth/register", json={"username": "byte_limit_user", "password": "密" * 30}
    )
    assert response.status_code == 422
    assert "72" in response.json()["detail"][0]["msg"]


async def test_forged_session_cookie_returns_401_not_500(client: AsyncClient) -> None:
    """故障注入：伪造 cookie 任何解析失败都按未认证处理，绝不 500。"""
    for forged in ("garbage", "a.b.c", "eyJhbGciOiJIUzI1NiJ9.forged.signature"):
        client.cookies.set("session", forged)
        response = await client.get("/api/auth/me")
        assert response.status_code == 401, f"伪造值 {forged!r} 应 401"
        assert response.json()["detail"] == "未登录或会话已过期"
