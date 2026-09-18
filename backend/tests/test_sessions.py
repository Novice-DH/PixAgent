"""编辑会话测试：建会话、切图、历史、越权与参数边界。

断言依据 specs/editor-canvas：状态码与中文消息是硬契约；revision 只在
切换到不同资产时 +1；切换同一张完全 no-op；历史线性封顶按 seq 倒序。
造图与上传复用 test_assets 的内存辅助，不新造 fixture 文件。
"""
import uuid

import pytest
from httpx import AsyncClient
from test_assets import _png_bytes, _register_and_get_client, _upload

from app.services.sessions import DEFAULT_TITLE

SESSION_NOT_FOUND = "会话不存在"
ASSET_NOT_FOUND = "素材不存在"


async def _create_session(
    client: AsyncClient, current: str, walls: list[str] | None = None, title: str | None = "会话"
):
    payload: dict = {"current_asset_id": current}
    if walls is not None:
        payload["asset_ids"] = walls
    if title is not None:
        payload["title"] = title
    return await client.post("/api/sessions", json=payload)


async def _upload_two_assets(client: AsyncClient) -> tuple[str, str, dict, dict]:
    first = await _upload(client, _png_bytes((320, 240)))
    second = await _upload(client, _png_bytes((200, 100)))
    assert first.status_code == 201 and second.status_code == 201
    first_body, second_body = first.json(), second.json()
    return first_body["id"], second_body["id"], first_body, second_body


# ---- 建会话 ----


async def test_create_session_returns_detail_with_document_and_wall(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    b1 = await _upload(client, _png_bytes((300, 300)))
    b2 = await _upload(client, _png_bytes((150, 90)))
    ids = [
        (await _upload(client, _png_bytes((320, 240)))).json()["id"],
        b1.json()["id"],
        b2.json()["id"],
    ]

    # 空白折叠 + 重复 id（b1 出现两次）只进一次 + current 自动进墙
    response = await _create_session(
        client, current=ids[0], walls=[ids[1], ids[1], ids[2]], title="  我的   会话  "
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["revision"] == 1
    assert body["title"] == "我的 会话"
    assert body["current_asset_id"] == ids[0]

    # document：画布尺寸 = 图片尺寸，单层锁定底图
    doc = body["document"]
    assert doc["width"] == 320 and doc["height"] == 240
    assert len(doc["layers"]) == 1
    layer = doc["layers"][0]
    assert layer["id"] == "base"
    assert layer["kind"] == "image"
    assert layer["name"] == "底图"
    assert layer["width"] == 320 and layer["height"] == 240
    assert layer["asset_id"] == ids[0]
    assert layer["locked"] is True
    assert layer["visible"] is True
    assert layer["opacity"] == 1
    assert layer["transform"] == {"x": 0, "y": 0, "scale_x": 1, "scale_y": 1, "rotation": 0}

    # 图片墙：current 优先 position=1，其余按传入顺序，重复 id 只进一次
    wall = body["wall"]
    assert [w["position"] for w in wall] == [1, 2, 3]
    assert [w["asset"]["id"] for w in wall] == [ids[0], ids[1], ids[2]]
    assert all("X-Amz-Signature" in w["asset"]["url"] for w in wall)

    # 历史：create_session，params {}、result {asset_id}
    history = (await client.get(f"/api/sessions/{body['id']}/history")).json()
    assert len(history) == 1
    assert history[0]["seq"] == 1
    assert history[0]["action"] == "create_session"
    assert history[0]["params"] == {}
    assert history[0]["result"] == {"asset_id": ids[0]}


@pytest.mark.parametrize("title", [None, "   ", "　"])
async def test_create_session_blank_title_becomes_default(client, credentials, title) -> None:
    await _register_and_get_client(client, credentials["username"])
    asset_id = (await _upload(client, _png_bytes())).json()["id"]

    payload: dict = {"current_asset_id": asset_id}
    if title is not None:
        payload["title"] = title
    response = await client.post("/api/sessions", json=payload)

    assert response.status_code == 201
    assert response.json()["title"] == DEFAULT_TITLE


async def test_create_session_unknown_current_asset_returns_404(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])

    response = await _create_session(client, current=str(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["detail"] == ASSET_NOT_FOUND


async def test_create_session_unknown_wall_asset_returns_404(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    asset_id = (await _upload(client, _png_bytes())).json()["id"]

    response = await _create_session(client, current=asset_id, walls=[str(uuid.uuid4())])

    assert response.status_code == 404
    assert response.json()["detail"] == ASSET_NOT_FOUND


async def test_create_session_too_many_asset_ids_returns_422(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    asset_id = (await _upload(client, _png_bytes())).json()["id"]
    walls = [str(uuid.uuid4()) for _ in range(13)]

    response = await _create_session(client, current=asset_id, walls=walls)

    assert response.status_code == 422


async def test_create_session_requires_auth(client) -> None:
    asset_id = uuid.uuid4()
    response = await client.post("/api/sessions", json={"current_asset_id": str(asset_id)})

    assert response.status_code == 401
    assert response.json()["detail"] == "未登录或会话已过期"


# ---- 切图与 revision ----


async def test_switch_current_bumps_revision_and_rebuilds_document(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, a2, _, _ = await _upload_two_assets(client)
    session_id = (await _create_session(client, current=a1, title="切换")).json()["id"]

    response = await client.patch(f"/api/sessions/{session_id}", json={"current_asset_id": a2})

    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 2
    assert body["current_asset_id"] == a2

    # document 整体重建：画布尺寸随新图变化，底图指向新资产
    doc = body["document"]
    assert doc["width"] == 200 and doc["height"] == 100
    assert doc["layers"][0]["asset_id"] == a2
    assert doc["layers"][0]["locked"] is True

    # 新图进墙且不挤掉旧图
    wall = body["wall"]
    assert [w["asset"]["id"] for w in wall] == [a1, a2]
    assert [w["position"] for w in wall] == [1, 2]

    # 历史追加 switch_current：params/result 精确
    history = (await client.get(f"/api/sessions/{session_id}/history")).json()
    assert [h["seq"] for h in history] == [2, 1]
    assert history[0]["action"] == "switch_current"
    assert history[0]["params"] == {"asset_id": a2}
    assert history[0]["result"] == {"revision": 2}


async def test_switch_back_to_existing_wall_asset_does_not_duplicate(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, a2, _, _ = await _upload_two_assets(client)
    session_id = (await _create_session(client, current=a1)).json()["id"]
    await client.patch(f"/api/sessions/{session_id}", json={"current_asset_id": a2})

    # 切回 a1（墙内已有）：revision 继续递增但墙不重复
    response = await client.patch(f"/api/sessions/{session_id}", json={"current_asset_id": a1})

    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 3
    assert [w["asset"]["id"] for w in body["wall"]] == [a1, a2]
    history = (await client.get(f"/api/sessions/{session_id}/history")).json()
    assert [h["seq"] for h in history] == [3, 2, 1]


async def test_switch_same_asset_is_noop(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, _, _, _ = await _upload_two_assets(client)
    session_id = (await _create_session(client, current=a1)).json()["id"]

    response = await client.patch(f"/api/sessions/{session_id}", json={"current_asset_id": a1})

    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert body["current_asset_id"] == a1
    assert len(body["wall"]) == 1
    # 完全 no-op：历史不追加、updated_at 不变
    history = (await client.get(f"/api/sessions/{session_id}/history")).json()
    assert len(history) == 1
    detail = (await client.get(f"/api/sessions/{session_id}")).json()
    assert detail["updated_at"] == body["updated_at"]


async def test_switch_to_unknown_asset_returns_404(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, _, _, _ = await _upload_two_assets(client)
    session_id = (await _create_session(client, current=a1)).json()["id"]

    response = await client.patch(
        f"/api/sessions/{session_id}", json={"current_asset_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == ASSET_NOT_FOUND


# ---- 改标题与空 PATCH ----


async def test_patch_title_normalizes(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, _, _, _ = await _upload_two_assets(client)
    session_id = (await _create_session(client, current=a1, title="旧标题")).json()["id"]

    renamed = await client.patch(f"/api/sessions/{session_id}", json={"title": "  新  标题 "})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "新 标题"
    assert renamed.json()["revision"] == 1  # 改标题不动 revision

    blanked = await client.patch(f"/api/sessions/{session_id}", json={"title": "   "})
    assert blanked.status_code == 200
    assert blanked.json()["title"] == DEFAULT_TITLE


async def test_patch_empty_object_changes_nothing(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, a2, _, _ = await _upload_two_assets(client)
    session_id = (await _create_session(client, current=a1, title="保持")).json()["id"]
    before = (await client.get(f"/api/sessions/{session_id}")).json()
    history_before = (await client.get(f"/api/sessions/{session_id}/history")).json()

    response = await client.patch(f"/api/sessions/{session_id}", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == before["revision"] == 1
    assert body["title"] == before["title"] == "保持"
    assert body["current_asset_id"] == before["current_asset_id"] == a1
    assert body["updated_at"] == before["updated_at"]
    history_after = (await client.get(f"/api/sessions/{session_id}/history")).json()
    assert history_after == history_before
    # a2 未受影响地留在素材库（没有被静默消费）
    assets = (await client.get("/api/assets")).json()
    assert {a["id"] for a in assets} == {a1, a2}


# ---- 列表与越权 ----


async def test_list_sessions_newest_first_with_limit(client, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, a2, _, _ = await _upload_two_assets(client)
    first = (await _create_session(client, current=a1, title="第一")).json()
    second = (await _create_session(client, current=a2, title="第二")).json()

    listing = await client.get("/api/sessions")
    assert listing.status_code == 200
    rows = listing.json()
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    assert all("document" not in r and "wall" not in r for r in rows)  # 摘要不含 document

    limited = await client.get("/api/sessions?limit=1")
    assert [r["id"] for r in limited.json()] == [second["id"]]


@pytest.mark.parametrize("limit", [0, 201])
async def test_list_sessions_limit_boundary_422(client, credentials, limit) -> None:
    await _register_and_get_client(client, credentials["username"])
    response = await client.get(f"/api/sessions?limit={limit}")
    assert response.status_code == 422


async def test_cross_user_detail_404_and_list_empty(client, credentials, other_credentials) -> None:
    await _register_and_get_client(client, credentials["username"])
    a1, _, _, _ = await _upload_two_assets(client)
    session_id = (await _create_session(client, current=a1, title="私有")).json()["id"]

    await _register_and_get_client(client, other_credentials["username"])

    detail = await client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 404
    assert detail.json()["detail"] == SESSION_NOT_FOUND

    history = await client.get(f"/api/sessions/{session_id}/history")
    assert history.status_code == 404
    assert history.json()["detail"] == SESSION_NOT_FOUND

    listing = await client.get("/api/sessions")
    assert listing.status_code == 200
    assert listing.json() == []


async def test_session_endpoints_require_auth(client) -> None:
    session_id = uuid.uuid4()
    assert (await client.get("/api/sessions")).status_code == 401
    assert (await client.get(f"/api/sessions/{session_id}")).status_code == 401
    assert (await client.get(f"/api/sessions/{session_id}/history")).status_code == 401
    assert (
        await client.patch(f"/api/sessions/{session_id}", json={"title": "x"})
    ).status_code == 401
