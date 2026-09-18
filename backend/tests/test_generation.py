"""生图链路任务级测试：受理、任务函数直呼、幂等、参数校验、越权与 SSE 快照重放。

任务级测试直呼任务函数、不经真实 ARQ broker（enqueue 由夹具拦截）；
端到端验证交给 scripts/e2e_generation.py。断言依据 specs/generation：
状态码与中文消息是硬契约。
"""
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from httpx import AsyncClient

from app import queue
from app.main import app

RUN_NOT_FOUND = "任务不存在"
REFERENCE_NOT_FOUND = "参考图不存在"


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """拦截队列投递：任务级测试不经真实 ARQ broker（零消息设施依赖）。"""
    enqueued: list[tuple[str, str]] = []

    async def fake_enqueue(task: str, run_id: uuid.UUID) -> None:
        enqueued.append((task, str(run_id)))

    monkeypatch.setattr(queue, "enqueue", fake_enqueue)
    yield enqueued


async def _register(client: AsyncClient, username: str) -> None:
    response = await client.post(
        "/api/auth/register", json={"username": username, "password": "test-password-123"}
    )
    assert response.status_code == 201, response.text


@asynccontextmanager
async def _second_client() -> AsyncIterator[AsyncClient]:
    """第二个独立会话：跨用户用例需要两个互不共享 Cookie 的客户端。"""
    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as other:
        yield other


async def _create_run(client: AsyncClient, **overrides) -> dict:
    payload = {"prompt": "一张白瓷茶壶的商品图，柔和自然光", "ratio": "4:5", "count": 4}
    payload.update(overrides)
    response = await client.post("/api/generations", json=payload)
    assert response.status_code == 202, response.text
    return response.json()


async def _run_task(run_id: str) -> None:
    """直呼任务函数：与 Worker 执行同一入口，不经队列。"""
    from app.tasks import TASKS

    await TASKS["generate_images"]({}, run_id)


async def _read_sse_frames(client: AsyncClient, run_id: str) -> list[dict]:
    """逐行解析 SSE：收集全部 data 帧（终态重放场景应只有一帧且连接关闭）。"""
    frames: list[dict] = []
    async with client.stream("GET", f"/events/runs/{run_id}") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[len("data: ") :]))
    return frames


async def test_create_generation_returns_202_queued(client: AsyncClient, credentials) -> None:
    await _register(client, credentials["username"])

    run = await _create_run(client)

    assert run["status"] == "queued"
    assert run["candidates"] == []
    assert run["tool"] == "generate_image"
    assert run["progress"] == 0


async def test_task_function_produces_candidates_of_requested_size(
    client: AsyncClient, credentials
) -> None:
    await _register(client, credentials["username"])
    run = await _create_run(client)

    await _run_task(run["id"])

    updated = (await client.get(f"/api/runs/{run['id']}")).json()
    assert updated["status"] == "succeeded"
    assert updated["progress"] == 100
    assert len(updated["candidates"]) == 4
    for candidate in updated["candidates"]:
        assert candidate["width"] == 1080
        assert candidate["height"] == 1350
        assert candidate["url"].startswith("http")


async def test_terminal_run_retask_does_not_duplicate(
    client: AsyncClient, credentials
) -> None:
    """终态短路：已 succeeded 的 run 再投递（直呼任务函数）不产生第二份结果。"""
    await _register(client, credentials["username"])
    run = await _create_run(client)

    await _run_task(run["id"])
    await _run_task(run["id"])  # 重复消费（worker 重启重投的等价物）

    updated = (await client.get(f"/api/runs/{run['id']}")).json()
    assert updated["status"] == "succeeded"
    assert len(updated["candidates"]) == 4


async def test_task_fallback_marks_failed_when_execution_crashes(
    client: AsyncClient, credentials, monkeypatch
) -> None:
    """兜底落败：执行崩溃 → rollback → 经任务参数重载落 FAILED（订阅方不空等）。"""
    from app.services import generation

    await _register(client, credentials["username"])
    run = await _create_run(client)

    async def explode(session, run):
        raise RuntimeError("模拟未预期崩溃")

    monkeypatch.setattr(generation, "execute", explode)
    await _run_task(run["id"])

    updated = (await client.get(f"/api/runs/{run['id']}")).json()
    assert updated["status"] == "failed"
    assert updated["error"] == "生成失败，请重试"


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": "   "},  # strip 后空白
        {"prompt": ""},  # 空字符串
        {"ratio": "3:2"},  # 未知比例
        {"count": 0},  # count 越界（下）
        {"count": 7},  # count 越界（上）
        {"negative_prompt": "x" * 1501},  # 负向词超长
        {"seed": 2147483648},  # seed 超上界
        {"reference_asset_ids": [str(uuid.uuid4()) for _ in range(4)]},  # 参考图超 3 个
    ],
)
async def test_invalid_input_returns_422(client: AsyncClient, credentials, payload) -> None:
    await _register(client, credentials["username"])

    response = await client.post("/api/generations", json={"prompt": "合理描述", **payload})

    assert response.status_code == 422


async def test_unknown_reference_asset_returns_404(client: AsyncClient, credentials) -> None:
    await _register(client, credentials["username"])

    response = await client.post(
        "/api/generations",
        json={
            "prompt": "带参考图的生成",
            "reference_asset_ids": [str(uuid.uuid4())],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == REFERENCE_NOT_FOUND


async def test_create_generation_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/generations", json={"prompt": "未登录也要生成"})

    assert response.status_code == 401
    assert response.json()["detail"] == "未登录或会话已过期"


async def test_run_cross_user_returns_404(
    client: AsyncClient, credentials, other_credentials
) -> None:
    await _register(client, credentials["username"])
    run = await _create_run(client)

    async with _second_client() as other:
        await _register(other, other_credentials["username"])

        response = await other.get(f"/api/runs/{run['id']}")

    assert response.status_code == 404
    assert response.json()["detail"] == RUN_NOT_FOUND


async def test_sse_terminal_run_replays_one_snapshot_and_closes(
    client: AsyncClient, credentials
) -> None:
    """刷新恢复路径：已终态任务重放一帧快照后立即关闭，重连与首连语义一致。"""
    await _register(client, credentials["username"])
    run = await _create_run(client)
    await _run_task(run["id"])

    frames = await _read_sse_frames(client, run["id"])

    assert len(frames) == 1
    assert frames[0]["id"] == run["id"]
    assert frames[0]["status"] == "succeeded"
    assert frames[0]["progress"] == 100


async def test_sse_cross_user_returns_404(
    client: AsyncClient, credentials, other_credentials
) -> None:
    await _register(client, credentials["username"])
    run = await _create_run(client)

    async with _second_client() as other:
        await _register(other, other_credentials["username"])

        response = await other.get(f"/events/runs/{run['id']}")

    assert response.status_code == 404
    assert response.json()["detail"] == RUN_NOT_FOUND
