"""对话链路测试：FakePlanner 规划替身（零 LLM 费用、不碰网络）+ 无 key 失败路径。

断言依据 specs/agent-tools：状态码与中文消息是硬契约；规划失败也落一轮；
verify 是安全边界——未注册工具与非法参数都被拒绝；工具产出进图片墙但不切
当前图。造图与上传复用 test_assets 的内存辅助。
"""
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, SystemMessage
from test_assets import _png_bytes, _register_and_get_client, _upload

from app import queue
from app.agent import graph as agent_graph
from app.agent.llm import planner
from app.config import get_settings

SESSION_NOT_FOUND = "会话不存在"


@pytest.fixture(autouse=True)
def _fresh_planner_cache():
    """planner 是 lru_cache：每个用例前后清缓存，防旧绑定"莫名"通过/失败。"""
    planner.cache_clear()
    yield
    planner.cache_clear()


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """拦截队列投递：任务级测试不经真实 ARQ broker（零消息设施依赖）。"""
    enqueued: list[tuple[str, str]] = []

    async def fake_enqueue(task: str, run_id: uuid.UUID) -> None:
        enqueued.append((task, str(run_id)))

    monkeypatch.setattr(queue, "enqueue", fake_enqueue)
    yield enqueued


class FakePlanner:
    """规划替身：记录收到的 messages、返回预置 AIMessage。"""

    def __init__(self, message: AIMessage) -> None:
        self.message = message
        self.calls: list[list[Any]] = []

    async def ainvoke(self, messages: list[Any], config: dict | None = None) -> AIMessage:
        self.calls.append(messages)
        return self.message


def _install_planner(monkeypatch, message: AIMessage) -> FakePlanner:
    """替换 graph 模块的 planner 引用（缓存绑定发生在 import 期，patch llm 原模块无效）。"""
    fake = FakePlanner(message)
    monkeypatch.setattr(agent_graph, "planner", lambda: fake)
    return fake


def _text_reply(text: str) -> AIMessage:
    return AIMessage(content=text, tool_calls=[])


def _tool_call(tool: str, args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": tool, "args": args, "id": call_id}])


async def _setup_session(client: AsyncClient, credentials: dict) -> dict:
    """注册 + 上传一张图 + 建会话；返回会话详情 body。"""
    await _register_and_get_client(client, credentials["username"])
    upload = await _upload(client, _png_bytes((320, 240)))
    asset_id = upload.json()["id"]
    response = await client.post(
        "/api/sessions", json={"current_asset_id": asset_id, "title": "对话测试"}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _send(client: AsyncClient, session_id: str, text: str) -> dict:
    response = await client.post(f"/api/sessions/{session_id}/messages", json={"text": text})
    assert response.status_code == 201, response.text
    return response.json()


# ---- 规划下发 ----


async def test_message_plans_and_dispatches_tool(
    client: AsyncClient, credentials, monkeypatch, _no_broker
) -> None:
    body = await _setup_session(client, credentials)
    _install_planner(
        monkeypatch, _tool_call("generate_image", {"prompt": "纯白背景商品图", "count": 2})
    )

    turn = await _send(client, body["id"], "换一张纯白背景的图")

    assert turn["status"] == "succeeded"
    assert turn["reply"] == "好，正在生成图片。"
    assert len(turn["steps"]) == 1
    step = turn["steps"][0]
    assert step["tool"] == "generate_image"
    assert step["label"] == "生成图片"
    assert step["run_id"]
    assert _no_broker == [("run_tool", step["run_id"])]


async def test_plain_text_reply_has_no_steps(
    client: AsyncClient, credentials, monkeypatch, _no_broker
) -> None:
    body = await _setup_session(client, credentials)
    _install_planner(monkeypatch, _text_reply("做不到，这张图没有可改的内容。"))

    turn = await _send(client, body["id"], "帮我把月亮 P 进去")

    assert turn["status"] == "succeeded"
    assert turn["reply"] == "做不到，这张图没有可改的内容。"
    assert turn["steps"] == []
    assert _no_broker == []


async def test_system_prompt_contains_canvas_facts(
    client: AsyncClient, credentials, monkeypatch
) -> None:
    body = await _setup_session(client, credentials)
    fake = _install_planner(monkeypatch, _text_reply("好"))

    await _send(client, body["id"], "画布上有什么")

    system = fake.calls[0][0]
    assert isinstance(system, SystemMessage)
    assert "画幅 320×240" in system.content
    assert "修订号 1" in system.content


async def test_unknown_tool_rejected(
    client: AsyncClient, credentials, monkeypatch, _no_broker
) -> None:
    body = await _setup_session(client, credentials)
    _install_planner(monkeypatch, _tool_call("generate_background", {"prompt": "海滩"}))

    turn = await _send(client, body["id"], "换个海滩背景")

    assert turn["status"] == "succeeded"  # 规划本身成功，被拒绝的是不可执行的步骤
    assert turn["reply"].startswith("这一步暂时执行不了")
    assert "generate_background" in turn["reply"]
    assert turn["steps"] == []
    assert _no_broker == []


async def test_invalid_params_rejected(
    client: AsyncClient, credentials, monkeypatch, _no_broker
) -> None:
    body = await _setup_session(client, credentials)
    _install_planner(monkeypatch, _tool_call("generate_image", {"count": 0}))

    turn = await _send(client, body["id"], "生成四张图")

    assert turn["reply"].startswith("这一步暂时执行不了")
    assert turn["steps"] == []
    assert _no_broker == []


async def test_tool_output_goes_to_wall_without_switching_current(
    client: AsyncClient, credentials, monkeypatch
) -> None:
    body = await _setup_session(client, credentials)
    _install_planner(
        monkeypatch, _tool_call("generate_image", {"prompt": "白背景商品图", "count": 2})
    )

    turn = await _send(client, body["id"], "换一张纯白背景的图")
    run_id = turn["steps"][0]["run_id"]

    # 直呼任务函数：与 Worker 执行同一入口，不经队列
    from app.tasks import TASKS

    await TASKS["run_tool"]({}, run_id)

    detail = (await client.get(f"/api/sessions/{body['id']}")).json()
    assert len(detail["wall"]) == len(body["wall"]) + 2  # 两张候选并入图片墙
    assert detail["current_asset_id"] == body["current_asset_id"]  # 当前图不变
    assert detail["revision"] == body["revision"]  # revision 不变

    history = (await client.get(f"/api/sessions/{body['id']}/history")).json()
    assert history[0]["action"] == "generate_image"  # 历史按 seq 倒序，最新一条是工具名
    assert history[0]["result"]["asset_ids"]


async def test_messages_returned_in_chronological_order(
    client: AsyncClient, credentials, monkeypatch
) -> None:
    body = await _setup_session(client, credentials)
    fake = _install_planner(monkeypatch, _text_reply("第一条回复"))

    first = await _send(client, body["id"], "第一句话")
    fake.message = _text_reply("第二条回复")
    second = await _send(client, body["id"], "第二句话")

    assert first["reply"] == "第一条回复"
    assert second["reply"] == "第二条回复"

    turns = (await client.get(f"/api/sessions/{body['id']}/messages")).json()
    assert [t["goal"] for t in turns] == ["第一句话", "第二句话"]


# ---- 无 key 失败路径 ----


async def test_missing_api_key_fails_turn_with_key_name(
    client: AsyncClient, credentials
) -> None:
    body = await _setup_session(client, credentials)
    settings = get_settings()
    original = settings.dashscope_api_key
    settings.dashscope_api_key = ""  # 防本机 .env 漂移：本用例必须走无 key 路径
    planner.cache_clear()
    try:
        turn = await _send(client, body["id"], "换一张纯白背景的图")
    finally:
        settings.dashscope_api_key = original
        planner.cache_clear()

    assert turn["status"] == "failed"
    assert "DASHSCOPE_API_KEY" in turn["error"]
    assert turn["steps"] == []

    # 规划失败也落库：刷新后该轮仍在
    turns = (await client.get(f"/api/sessions/{body['id']}/messages")).json()
    assert turns[-1]["status"] == "failed"


# ---- 协议边界 ----


async def test_blank_message_returns_422(client: AsyncClient, credentials) -> None:
    body = await _setup_session(client, credentials)

    response = await client.post(f"/api/sessions/{body['id']}/messages", json={"text": "   "})

    assert response.status_code == 422


async def test_message_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/sessions/{uuid.uuid4()}/messages", json={"text": "未登录也要说话"}
    )

    assert response.status_code == 401


async def test_message_unknown_session_returns_404(client: AsyncClient, credentials) -> None:
    await _register_and_get_client(client, credentials["username"])

    response = await client.post(
        f"/api/sessions/{uuid.uuid4()}/messages", json={"text": "会话不存在"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == SESSION_NOT_FOUND


# ---- S13 选区事实注入 ----


async def _select_point(client: AsyncClient, session_id: str, revision: int) -> None:
    from httpx import AsyncClient as _Client  # noqa: F401  仅类型提示用途

    response = await client.post(
        f"/api/sessions/{session_id}/selection",
        json={"revision": revision, "points": [{"x": 0.5, "y": 0.5}]},
    )
    assert response.status_code == 200, response.text


async def test_canvas_summary_reports_no_selection(
    client: AsyncClient, credentials, monkeypatch
) -> None:
    body = await _setup_session(client, credentials)
    fake = _install_planner(monkeypatch, _text_reply("好"))

    await _send(client, body["id"], "画布上有什么")

    system = fake.calls[0][0]
    assert "当前无选区" in system.content


async def test_canvas_summary_reports_point_selection(
    client: AsyncClient, credentials, monkeypatch
) -> None:
    body = await _setup_session(client, credentials)
    await _select_point(client, body["id"], body["revision"])
    fake = _install_planner(monkeypatch, _text_reply("好"))

    await _send(client, body["id"], "画布上有什么")

    system = fake.calls[0][0]
    assert "已有选区，1 个标点" in system.content


async def test_selection_summary_dispatches_replace_region_directly(
    client: AsyncClient, credentials, monkeypatch, _no_broker
) -> None:
    """已有选区时规划器直接派 replace_region，不再反问重选。"""
    body = await _setup_session(client, credentials)
    await _select_point(client, body["id"], body["revision"])
    fake = _install_planner(monkeypatch, _tool_call("replace_region", {"prompt": "黑色"}))

    turn = await _send(client, body["id"], "把选区里的东西换成黑色")

    assert turn["status"] == "succeeded"
    assert turn["steps"][0]["tool"] == "replace_region"  # 一步到位
    assert turn["steps"][0]["run_id"]
    system = fake.calls[0][0]
    assert "已有选区" in system.content
