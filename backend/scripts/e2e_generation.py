"""端到端链路验证（验收 C）：mock Provider 全链路七步，零费用。

运行前提：compose 三件套（PG/Redis/MinIO）+ `uv run arq app.worker.WorkerSettings`
+ `uv run uvicorn app.main:app` 已在本机运行。
trust_env=False：避免代理环境变量劫持本地请求。
"""
import json
import sys
import uuid

import httpx

BASE_URL = "http://127.0.0.1:7302"
USERNAME = "e2e_gen"
PASSWORD = "e2e-password-123"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}

results: list[tuple[int, str, bool, str]] = []


def record(step: int, name: str, ok: bool, detail: str = "") -> None:
    results.append((step, name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] 第 {step} 步 {name}" + (f" —— {detail}" if detail else ""))


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, trust_env=False, timeout=60.0)

    # 第 1 步：登录（重复注册 409 自动转登录，脚本可重复执行）
    print("=== 第 1 步 登录 ===")
    register = client.post(
        "/api/auth/register", json={"username": USERNAME, "password": PASSWORD}
    )
    if register.status_code == 201:
        print("注册成功，会话已建立")
    elif register.status_code == 409:
        print("账号已存在（409），转登录")
        login = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        assert login.status_code == 200, login.text
        print("登录成功，会话已建立")
    else:
        raise AssertionError(f"注册返回异常状态 {register.status_code}: {register.text}")
    record(1, "登录（重复注册 409 自动转登录）", client.cookies.get("session") is not None)

    # 第 2 步：发起生成（202 受理）
    print("\n=== 第 2 步 发起生成 ===")
    response = client.post(
        "/api/generations",
        json={"prompt": "磨砂玻璃瓶装的柑橘调香水，晨光窗台，浅色背景", "ratio": "4:5", "count": 4},
    )
    print(f"POST /api/generations → {response.status_code}")
    run = response.json()
    print("RunOut:", json.dumps(run, ensure_ascii=False))
    run_id = run.get("id")
    record(
        2,
        "发起生成 202 且状态 queued",
        response.status_code == 202 and run.get("status") == "queued" and run_id is not None,
    )

    # 第 3 步：SSE 逐帧到终态 succeeded
    print("\n=== 第 3 步 SSE 进度流 ===")
    frames: list[dict] = []
    with client.stream("GET", f"/events/runs/{run_id}") as stream:
        assert stream.status_code == 200, stream.status_code
        assert stream.headers["content-type"].startswith("text/event-stream")
        for line in stream.iter_lines():
            if line.startswith("data: "):
                frame = json.loads(line[len("data: ") :])
                frames.append(frame)
                print(
                    f"SSE 帧: status={frame['status']} progress={frame['progress']} "
                    f"stage={frame['stage']}"
                )
            elif line.startswith(":"):
                print("SSE 心跳:", line)
            if frames and frames[-1]["status"] in TERMINAL_STATUSES:
                break
    progress_values = [frame["progress"] for frame in frames]
    record(
        3,
        "SSE 逐帧到终态 succeeded（单调推进）",
        bool(frames)
        and frames[-1]["status"] == "succeeded"
        and progress_values == sorted(progress_values)
        and len(frames) > 1,
        f"共 {len(frames)} 帧，progress 序列 {progress_values}",
    )

    # 第 4 步：候选 4 张且尺寸 1080×1350（4:5）
    print("\n=== 第 4 步 候选快照 ===")
    snapshot = client.get(f"/api/runs/{run_id}").json()
    candidates = snapshot.get("candidates", [])
    print(
        f"status={snapshot['status']} 候选数={len(candidates)} "
        f"尺寸={[(c['width'], c['height']) for c in candidates]}"
    )
    record(
        4,
        "候选 4 张且尺寸 1080×1350",
        len(candidates) == 4
        and all(c["width"] == 1080 and c["height"] == 1350 for c in candidates),
    )

    # 第 5 步：匿名下载签名 URL 得到 PNG
    print("\n=== 第 5 步 匿名签名 URL 下载 ===")
    anonymous = httpx.Client(trust_env=False, timeout=60.0)  # 不带任何 Cookie
    download = anonymous.get(candidates[0]["url"])
    head = download.content[:8]
    print(f"GET 签名 URL（匿名）→ {download.status_code} 前 8 字节 = {head!r}")
    record(5, "匿名下载签名 URL 得到 PNG", download.status_code == 200 and head == PNG_MAGIC)
    anonymous.close()

    # 第 6 步：空 prompt 422
    print("\n=== 第 6 步 参数校验 ===")
    invalid = client.post("/api/generations", json={"prompt": "   "})
    print(f"POST 空 prompt → {invalid.status_code}")
    record(6, "空 prompt 422", invalid.status_code == 422)

    # 第 7 步：未登录读任务 401
    print("\n=== 第 7 步 未登录访问 ===")
    stranger = httpx.Client(trust_env=False, timeout=60.0)  # 不带任何 Cookie
    denied = stranger.get(f"{BASE_URL}/api/runs/{run_id}")
    print(f"GET /api/runs/{{id}}（未登录）→ {denied.status_code}")
    record(7, "未登录读任务 401", denied.status_code == 401)
    stranger.close()
    client.close()

    print("\n=== 结果汇总 ===")
    all_ok = True
    for step, name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {step}. {name}" + (f" —— {detail}" if detail else ""))
        all_ok = all_ok and ok
    print("\n七步全过" if all_ok else "\n存在失败步骤")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
