"""工具与撤销端到端测试：202 受理即完成（同步文档工具）、队列像素工具、快照式 undo/redo。

断言依据 specs/deterministic-tools：同步工具 202 响应一次带回终态 run 与新会话
（不投队列）；像素工具产出直接采用为当前图；undo/redo 是快照恢复；新编辑截断
重做分支；并发撤销至多一次成功。造图与上传复用 test_assets 的内存辅助。
"""
import asyncio
import io
import uuid

import httpx
import pytest
from httpx import AsyncClient
from test_agent import _install_planner
from test_assets import _png_bytes, _register_and_get_client, _upload

from app import queue
from app.services import tools as tools_service

NO_UNDO = "没有可撤销的操作"
NO_REDO = "没有可重做的操作"
SESSION_REQUIRED = "此工具需要在编辑会话中使用"


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """拦截队列投递：像素工具直呼任务函数；同步文档工具必须零投递。"""
    enqueued: list[tuple[str, str]] = []

    async def fake_enqueue(task: str, run_id: uuid.UUID) -> None:
        enqueued.append((task, str(run_id)))

    monkeypatch.setattr(queue, "enqueue", fake_enqueue)
    yield enqueued


def _subject_png(size: tuple[int, int] = (64, 64)) -> bytes:
    """纯色绿底 + 中心红方块：corner 抠图与调色的标准试验图。"""
    from PIL import Image

    image = Image.new("RGBA", size, (0, 200, 0, 255))
    for x in range(size[0] // 4, size[0] * 3 // 4):
        for y in range(size[1] // 4, size[1] * 3 // 4):
            image.putpixel((x, y), (200, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def _setup(client: AsyncClient, credentials: dict, size: tuple[int, int] = (320, 240)):
    await _register_and_get_client(client, credentials["username"])
    upload = await _upload(client, _png_bytes(size))
    asset_id = upload.json()["id"]
    response = await client.post("/api/sessions", json={"current_asset_id": asset_id})
    assert response.status_code == 201, response.text
    return response.json()


async def _invoke(client: AsyncClient, session_id: str, tool: str, params: dict | None = None):
    return await client.post(
        f"/api/sessions/{session_id}/tools", json={"tool": tool, "params": params or {}}
    )


async def _run_task(run_id: str) -> None:
    from app.tasks import TASKS

    await TASKS["run_tool"]({}, run_id)


# ---- 同步文档工具 ----


async def test_flip_takes_effect_immediately_without_queue(
    client: AsyncClient, credentials, _no_broker
) -> None:
    body = await _setup(client, credentials)

    response = await _invoke(client, body["id"], "flip_layer", {"direction": "horizontal"})

    assert response.status_code == 202, response.text
    result = response.json()
    # 受理即完成：同步路径不投队列，响应一次带回终态 run 与新会话
    assert result["run"]["status"] == "succeeded"
    assert result["run"]["tool"] == "flip_layer"
    assert _no_broker == []
    assert result["session"]["document"]["layers"][0]["transform"]["scale_x"] == -1
    assert result["session"]["revision"] == body["revision"] + 1
    assert result["session"]["can_undo"] is True
    assert result["session"]["history_seq"] == 2


async def test_crop_to_square_resizes_canvas_and_translates_layer(
    client: AsyncClient, credentials
) -> None:
    body = await _setup(client, credentials, size=(1920, 1080))

    response = await _invoke(client, body["id"], "crop_canvas", {"ratio": "1:1"})

    assert response.status_code == 202, response.text
    doc = response.json()["session"]["document"]
    assert (doc["width"], doc["height"]) == (1080, 1080)
    assert doc["layers"][0]["transform"]["x"] == -420  # (1920-1080)/2 居中位移


async def test_successive_document_tools_compose(client: AsyncClient, credentials) -> None:
    body = await _setup(client, credentials)

    await _invoke(client, body["id"], "set_layer_opacity", {"opacity": 0.5})
    await _invoke(client, body["id"], "scale_layer", {"factor": 2})
    response = await _invoke(client, body["id"], "rotate_layer", {"angle": 45})

    transform = response.json()["session"]["document"]["layers"][0]["transform"]
    assert transform == {"x": 0, "y": 0, "scale_x": 2, "scale_y": 2, "rotation": 45}
    assert response.json()["session"]["document"]["layers"][0]["opacity"] == 0.5
    assert response.json()["session"]["can_undo"] is True


async def test_default_layer_is_topmost_visible_image(client: AsyncClient, credentials) -> None:
    body = await _setup(client, credentials)

    # 不传 layer_id：服务端解析为最上层可见图像层（Agent 路径的关键缺省）
    response = await _invoke(client, body["id"], "flip_layer", {"direction": "vertical"})

    assert response.status_code == 202
    assert response.json()["session"]["document"]["layers"][0]["transform"]["scale_y"] == -1


async def test_layer_id_resolves_missing_layer_to_failed_run(
    client: AsyncClient, credentials
) -> None:
    body = await _setup(client, credentials)

    response = await _invoke(
        client, body["id"], "flip_layer", {"direction": "horizontal", "layer_id": "ghost"}
    )

    assert response.status_code == 202  # 受理成功，执行失败——run 落 failed
    result = response.json()
    assert result["run"]["status"] == "failed"
    assert result["run"]["error"]
    assert result["session"]["document"]["layers"][0]["transform"]["scale_x"] == 1


# ---- 快照撤销 / 重做 ----


async def test_undo_redo_roundtrip_and_boundaries(client: AsyncClient, credentials) -> None:
    body = await _setup(client, credentials)
    await _invoke(client, body["id"], "flip_layer", {"direction": "horizontal"})

    undone = (await client.post(f"/api/sessions/{body['id']}/undo")).json()
    assert undone["document"]["layers"][0]["transform"]["scale_x"] == 1  # 恢复前文档
    assert undone["history_seq"] == body["history_seq"]
    assert undone["can_undo"] is False
    assert undone["can_redo"] is True

    redone = (await client.post(f"/api/sessions/{body['id']}/redo")).json()
    assert redone["document"]["layers"][0]["transform"]["scale_x"] == -1  # 重放
    assert redone["can_undo"] is True

    # 边界：撤无可撤（seq 1 是建会话）
    await client.post(f"/api/sessions/{body['id']}/undo")
    boundary = await client.post(f"/api/sessions/{body['id']}/undo")
    assert boundary.status_code == 409
    assert boundary.json()["detail"] == NO_UNDO
    redo_boundary = await client.post(f"/api/sessions/{body['id']}/redo")
    assert redo_boundary.status_code == 200  # seq 2 的 after 快照仍可重做
    await client.post(f"/api/sessions/{body['id']}/undo")
    extra = await client.post(f"/api/sessions/{body['id']}/redo")
    assert extra.status_code == 200
    await client.post(f"/api/sessions/{body['id']}/redo")
    last = await client.post(f"/api/sessions/{body['id']}/redo")
    assert last.status_code == 409
    assert last.json()["detail"] == NO_REDO


async def test_new_edit_after_undo_discards_redo_branch(
    client: AsyncClient, credentials
) -> None:
    body = await _setup(client, credentials)
    await _invoke(client, body["id"], "flip_layer", {"direction": "horizontal"})  # seq2: -1
    await _invoke(client, body["id"], "flip_layer", {"direction": "horizontal"})  # seq3: +1
    await client.post(f"/api/sessions/{body['id']}/undo")  # 回到 seq2：-1

    # undo 之后的新编辑：截断被撤的未来（旧 seq3），线性历史不接受分支
    fresh = await _invoke(client, body["id"], "set_layer_opacity", {"opacity": 0.5})
    assert fresh.status_code == 202
    session = fresh.json()["session"]
    assert session["document"]["layers"][0]["transform"]["scale_x"] == -1
    assert session["document"]["layers"][0]["opacity"] == 0.5
    assert session["can_redo"] is False

    redo = await client.post(f"/api/sessions/{body['id']}/redo")
    assert redo.status_code == 409
    assert redo.json()["detail"] == NO_REDO


async def test_concurrent_undo_only_one_wins(client: AsyncClient, credentials) -> None:
    body = await _setup(client, credentials)
    await _invoke(client, body["id"], "flip_layer", {"direction": "horizontal"})

    responses = await asyncio.gather(
        *[client.post(f"/api/sessions/{body['id']}/undo") for _ in range(5)]
    )
    codes = sorted(response.status_code for response in responses)
    assert codes == [200, 409, 409, 409, 409]  # 至多一次成功，其余 409，无 500
    final = (await client.get(f"/api/sessions/{body['id']}")).json()
    assert final["history_seq"] == body["history_seq"]  # 指针回到建会话，无脏文档
    assert final["document"]["layers"][0]["transform"]["scale_x"] == 1


# ---- 协议边界 ----


async def test_unknown_tool_404_and_invalid_params_422(
    client: AsyncClient, credentials
) -> None:
    body = await _setup(client, credentials)

    unknown = await _invoke(client, body["id"], "make_it_pretty")
    assert unknown.status_code == 404

    invalid = await _invoke(client, body["id"], "set_layer_opacity", {"opacity": 5})
    assert invalid.status_code == 422

    ambiguous = await _invoke(
        client,
        body["id"],
        "crop_canvas",
        {"ratio": "1:1", "rect": {"x": 0, "y": 0, "width": 0.5, "height": 0.5}},
    
    )
    assert ambiguous.status_code == 422


async def test_session_required_tool_without_session_rejected() -> None:
    """服务级守卫：session_required 工具缺会话上下文，受理期直接 InvalidParams。"""
    from app.db import SessionFactory

    async with SessionFactory() as session:
        with pytest.raises(tools_service.InvalidParams) as error:
            await tools_service.submit(session, uuid.uuid4(), "flip_layer", {})
        assert "编辑会话" in str(error.value)


async def test_tools_and_undo_require_auth(client: AsyncClient) -> None:
    assert (
        await client.post(f"/api/sessions/{uuid.uuid4()}/tools", json={"tool": "flip_layer"})
    ).status_code == 401
    assert (await client.post(f"/api/sessions/{uuid.uuid4()}/undo")).status_code == 401
    assert (await client.post(f"/api/sessions/{uuid.uuid4()}/redo")).status_code == 401


async def test_tools_unknown_session_404(client: AsyncClient, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])

    response = await _invoke(client, str(uuid.uuid4()), "flip_layer", {})

    assert response.status_code == 404


# ---- 像素工具（队列通道 + 直呼任务函数）----


async def test_remove_background_adopts_output(
    client: AsyncClient, credentials, _no_broker
) -> None:
    await _register_and_get_client(client, credentials["username"])
    upload = await _upload(client, _subject_png())
    session = (
        await client.post("/api/sessions", json={"current_asset_id": upload.json()["id"]})
    ).json()

    response = await _invoke(client, session["id"], "remove_background")

    assert response.status_code == 202
    result = response.json()
    run_id = result["run"]["id"]
    assert result["run"]["status"] == "queued"  # 异步工具受理即排队
    assert _no_broker == [("run_tool", run_id)]

    await _run_task(run_id)

    detail = (await client.get(f"/api/sessions/{session['id']}")).json()
    assert detail["current_asset_id"] != session["current_asset_id"]  # 产出直接采用
    assert detail["revision"] == session["revision"] + 1
    wall_ids = [w["asset"]["id"] for w in detail["wall"]]
    assert session["current_asset_id"] in wall_ids  # 旧图仍在墙
    adopted = next(w for w in detail["wall"] if w["asset"]["id"] == detail["current_asset_id"])
    assert adopted["asset"]["kind"] == "subject"
    assert adopted["asset"]["source"] == "tool"
    assert adopted["asset"]["has_alpha"] is True  # 透明通道为真
    assert detail["can_undo"] is True
    assert detail["document"]["layers"][0]["asset_id"] == detail["current_asset_id"]

    run = (await client.get(f"/api/runs/{run_id}")).json()
    assert run["status"] == "succeeded"


async def test_adjust_image_creates_asset_and_can_undo(
    client: AsyncClient, credentials, _no_broker
) -> None:
    await _register_and_get_client(client, credentials["username"])
    upload = await _upload(client, _subject_png())
    session = (
        await client.post("/api/sessions", json={"current_asset_id": upload.json()["id"]})
    ).json()

    response = await _invoke(
        client, session["id"], "adjust_image", {"brightness": 0.5, "vignette": 0.4}
    )

    assert response.status_code == 202
    run_id = response.json()["run"]["id"]
    await _run_task(run_id)

    detail = (await client.get(f"/api/sessions/{session['id']}")).json()
    assert detail["current_asset_id"] != session["current_asset_id"]
    adopted = next(w for w in detail["wall"] if w["asset"]["id"] == detail["current_asset_id"])
    assert adopted["asset"]["kind"] == "generated"
    assert adopted["asset"]["source"] == "tool"
    assert detail["can_undo"] is True

    undone = (await client.post(f"/api/sessions/{session['id']}/undo")).json()
    assert undone["current_asset_id"] == session["current_asset_id"]  # 快照恢复
    assert undone["revision"] == session["revision"]


async def test_pixel_tool_submit_with_queue_down_returns_503(
    client: AsyncClient, credentials, monkeypatch
) -> None:
    """队列不可达是环境故障：像素工具受理翻 503，API 不崩；同步文档工具不受影响。"""
    import redis.exceptions

    body = await _setup(client, credentials)

    async def broken_enqueue(task: str, run_id: uuid.UUID) -> None:
        raise redis.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(queue, "enqueue", broken_enqueue)
    pixel = await _invoke(client, body["id"], "remove_background")
    assert pixel.status_code == 503
    assert "队列服务暂时不可用" in pixel.json()["detail"]

    # 同步路径不碰队列：翻转照常受理即完成
    flip = await _invoke(client, body["id"], "flip_layer", {"direction": "horizontal"})
    assert flip.status_code == 202
    assert flip.json()["run"]["status"] == "succeeded"


async def test_remove_background_pixel_tool_failure_is_explicit(
    client: AsyncClient, credentials, _no_broker, monkeypatch
) -> None:
    """MATTING_PROVIDER=rembg 未装依赖：工具落 failed 且错误明确，不悬挂。"""
    from app.config import get_settings

    await _register_and_get_client(client, credentials["username"])
    upload = await _upload(client, _subject_png())
    session = (
        await client.post("/api/sessions", json={"current_asset_id": upload.json()["id"]})
    ).json()
    settings = get_settings()
    original = settings.matting_provider
    settings.matting_provider = "rembg"
    try:
        response = await _invoke(client, session["id"], "remove_background")
        run_id = response.json()["run"]["id"]
        await _run_task(run_id)
    finally:
        settings.matting_provider = original

    run = (await client.get(f"/api/runs/{run_id}")).json()
    assert run["status"] == "failed"
    assert "rembg" in run["error"]


# ---- Agent 派发画布工具 ----


async def test_agent_dispatches_canvas_tool(
    client: AsyncClient, credentials, monkeypatch, _no_broker
) -> None:
    from test_agent import _tool_call

    body = await _setup(client, credentials)
    _install_planner(monkeypatch, _tool_call("flip_layer", {"direction": "horizontal"}))

    turn_response = await client.post(
        f"/api/sessions/{body['id']}/messages", json={"text": "把图水平翻转"}
    )
    assert turn_response.status_code == 201
    turn = turn_response.json()
    assert turn["status"] == "succeeded"
    assert turn["steps"][0]["tool"] == "flip_layer"
    assert turn["steps"][0]["label"] == "翻转"

    # 文档工具同步执行：规划下发即完成，文档实际变化
    detail = (await client.get(f"/api/sessions/{body['id']}")).json()
    assert detail["document"]["layers"][0]["transform"]["scale_x"] == -1
    assert detail["can_undo"] is True


async def test_publish_failure_does_not_break_tools(
    client: AsyncClient, credentials, monkeypatch, _no_broker
) -> None:
    """进度帧是尽力而为的旁路：Redis 挂掉时发布失败只记日志，受理与执行照常。"""
    import redis.exceptions

    from app import events

    body = await _setup(client, credentials)

    async def broken_publish(channel: str, message: dict) -> None:
        raise redis.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(events, "publish_snapshot", broken_publish)
    flip = await _invoke(client, body["id"], "flip_layer", {"direction": "horizontal"})
    assert flip.status_code == 202
    assert flip.json()["run"]["status"] == "succeeded"


# ---- S12 生成式工具（mock Provider，直呼任务函数） ----


async def _run_and_detail(client: AsyncClient, session: dict, tool: str, params: dict):
    """受理 → 直呼任务函数 → 返回（终态 run、新会话详情）。"""
    response = await _invoke(client, session["id"], tool, params)
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["run"]["status"] == "queued"
    await _run_task(result["run"]["id"])
    run = (await client.get(f"/api/runs/{result['run']['id']}")).json()
    detail = (await client.get(f"/api/sessions/{session['id']}")).json()
    return run, detail


async def test_replace_background_single_adopts_and_can_undo(
    client: AsyncClient, credentials, _no_broker
) -> None:
    session = await _setup(client, credentials, size=(320, 240))

    run, detail = await _run_and_detail(
        client, session, "replace_background", {"prompt": "浅木色桌面，晨光从左侧照入"}
    )

    assert run["status"] == "succeeded"
    assert detail["current_asset_id"] != session["current_asset_id"]  # 单张直接采用
    assert detail["revision"] == session["revision"] + 1  # 采用是可撤销编辑
    assert detail["document"]["width"] == 320  # 换背景画幅不变
    assert detail["document"]["height"] == 240
    wall_ids = [w["asset"]["id"] for w in detail["wall"]]
    assert session["current_asset_id"] in wall_ids  # 旧图仍在墙
    adopted = next(w for w in detail["wall"] if w["asset"]["id"] == detail["current_asset_id"])
    assert adopted["asset"]["kind"] == "generated"
    assert adopted["asset"]["source"] == "tool"
    assert adopted["asset"]["width"] == 320 and adopted["asset"]["height"] == 240
    assert detail["can_undo"] is True

    undo = await client.post(f"/api/sessions/{session['id']}/undo")
    assert undo.status_code == 200
    undone = undo.json()
    assert undone["current_asset_id"] == session["current_asset_id"]  # 撤销回到原图
    assert undone["revision"] == session["revision"]


async def test_replace_background_multi_keeps_current(
    client: AsyncClient, credentials, _no_broker
) -> None:
    session = await _setup(client, credentials, size=(320, 240))
    wall_before = [w["asset"]["id"] for w in
                   (await client.get(f"/api/sessions/{session['id']}")).json()["wall"]]

    run, detail = await _run_and_detail(
        client, session, "replace_background", {"prompt": "海边日落", "count": 2}
    )

    assert run["status"] == "succeeded"
    assert detail["current_asset_id"] == session["current_asset_id"]  # 多候选不切当前图
    assert detail["revision"] == session["revision"]  # revision 不被候选污染
    new_entries = [w for w in detail["wall"] if w["asset"]["id"] not in wall_before]
    assert len(new_entries) == 2  # 图片墙新增 2 张候选
    assert all(
        w["asset"]["kind"] == "generated" and w["asset"]["source"] == "tool" for w in new_entries
    )
    assert all(w["asset"]["width"] == 320 and w["asset"]["height"] == 240 for w in new_entries)


async def test_expand_canvas_grows_to_cover_ratio(
    client: AsyncClient, credentials, _no_broker
) -> None:
    session = await _setup(client, credentials, size=(320, 240))

    run, detail = await _run_and_detail(
        client, session, "expand_canvas", {"ratio": "16:9"}
    )

    assert run["status"] == "succeeded"
    assert detail["document"]["width"] == 426  # 刚好包住原画的 16:9（cover_size）
    assert detail["document"]["height"] == 240
    assert detail["current_asset_id"] != session["current_asset_id"]  # 扩图总是直接采用
    assert detail["revision"] == session["revision"] + 1
    adopted = next(w for w in detail["wall"] if w["asset"]["id"] == detail["current_asset_id"])
    assert adopted["asset"]["width"] == 426 and adopted["asset"]["height"] == 240
    assert adopted["asset"]["kind"] == "generated"


async def test_upscale_doubles_dimensions(
    client: AsyncClient, credentials, _no_broker
) -> None:
    session = await _setup(client, credentials, size=(320, 240))

    run, detail = await _run_and_detail(client, session, "upscale_image", {"scale": 2})

    assert run["status"] == "succeeded"
    assert detail["document"]["width"] == 640  # document 跟随翻倍
    assert detail["document"]["height"] == 480
    assert detail["current_asset_id"] != session["current_asset_id"]  # 超分总是直接采用
    assert detail["revision"] == session["revision"] + 1
    adopted = next(w for w in detail["wall"] if w["asset"]["id"] == detail["current_asset_id"])
    assert adopted["asset"]["width"] == 640 and adopted["asset"]["height"] == 480


# ---- S12 故障注入（验收 E） ----


async def test_dashscope_without_key_fails_all_three_generative_tools(
    client: AsyncClient, credentials, _no_broker, monkeypatch
) -> None:
    """IMAGE_PROVIDER=dashscope 且无 key：三个新工具落 failed、错误含配置键名。"""
    from app.config import get_settings
    from app.providers import get_image_provider

    session = await _setup(client, credentials, size=(320, 240))
    settings = get_settings()
    monkeypatch.setattr(settings, "image_provider", "dashscope")
    get_image_provider.cache_clear()
    try:
        cases = [
            ("replace_background", {"prompt": "海边日落"}),
            ("expand_canvas", {"ratio": "16:9"}),
            ("upscale_image", {}),
        ]
        for tool, params in cases:
            response = await _invoke(client, session["id"], tool, params)
            assert response.status_code == 202, response.text
            run_id = response.json()["run"]["id"]
            await _run_task(run_id)
            run = (await client.get(f"/api/runs/{run_id}")).json()
            assert run["status"] == "failed", (tool, run)
            assert "DASHSCOPE_API_KEY" in run["error"], (tool, run["error"])
        # 会话无脏数据：当前图与 revision 均不变
        detail = (await client.get(f"/api/sessions/{session['id']}")).json()
        assert detail["current_asset_id"] == session["current_asset_id"]
        assert detail["revision"] == session["revision"]
    finally:
        get_image_provider.cache_clear()


def _install_edit_http_fault(monkeypatch, mode: str) -> None:
    """只对编辑端点路径注入故障：测试客户端自身也走 httpx.AsyncClient，不能整类替换。"""
    from app.providers.dashscope import _EDIT_PATH

    original_post = httpx.AsyncClient.post

    async def fake_post(self, path, json=None):
        if path == _EDIT_PATH:
            if mode == "timeout":
                raise httpx.TimeoutException("connect timeout")
            request = httpx.Request("POST", "http://test" + path)
            response = httpx.Response(500, request=request, text="server exploded")
            response.raise_for_status()
            return response
        return await original_post(self, path, json=json)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)


async def _invoke_edit_with_http_fault(
    client: AsyncClient, credentials: dict, _no_broker, monkeypatch, mode: str
) -> tuple[str, dict, str]:
    from app.config import get_settings
    from app.providers import get_image_provider

    session = await _setup(client, credentials, size=(320, 240))
    settings = get_settings()
    monkeypatch.setattr(settings, "image_provider", "dashscope")
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key-not-real")
    _install_edit_http_fault(monkeypatch, mode)
    get_image_provider.cache_clear()
    try:
        response = await _invoke(
            client, session["id"], "replace_background", {"prompt": "海边日落"}
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["run"]["id"]
        await _run_task(run_id)
        run = (await client.get(f"/api/runs/{run_id}")).json()
        detail = (await client.get(f"/api/sessions/{session['id']}")).json()
        return run["status"], run, detail
    finally:
        get_image_provider.cache_clear()




async def test_edit_timeout_surfaces_provider_error_without_dirty_session(
    client: AsyncClient, credentials, _no_broker, monkeypatch
) -> None:
    status, run, detail = await _invoke_edit_with_http_fault(
        client, credentials, _no_broker, monkeypatch, "timeout"
    )
    assert status == "failed"
    assert run["error"] == "模型服务编辑超时，请稍后重试"
    # 会话无脏数据：rollback 纪律下 revision 与 document 保持原样
    assert detail["current_asset_id"] is not None
    assert detail["revision"] == 1


async def test_edit_http_500_surfaces_provider_error_without_dirty_session(
    client: AsyncClient, credentials, _no_broker, monkeypatch
) -> None:
    status, run, detail = await _invoke_edit_with_http_fault(
        client, credentials, _no_broker, monkeypatch, "http-500"
    )
    assert status == "failed"
    assert run["error"] is not None and run["error"].startswith("模型服务编辑失败")
    assert detail["revision"] == 1
