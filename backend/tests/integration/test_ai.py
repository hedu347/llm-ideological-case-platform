"""AI 生成、问答与记录接口的集成测试。"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "123456"},
    )
    return response.json()["data"]["token"]


async def test_generate_stream_returns_sse_events(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """生成接口应返回 progress/content/done 事件。"""
    token = await _login(client, "teacher01")
    response = await client.post(
        "/api/v1/ai/generate",
        json={
            "ideological": "科技报国",
            "knowledge": "系统工程",
            "profession": ["航空航天工程"],
        },
        headers=auth(token),
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: progress" in response.text
    assert "event: content" in response.text
    assert "event: done" in response.text


async def test_generate_creates_record(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """生成完成后应可在记录列表看到。"""
    token = await _login(client, "teacher01")
    await client.post(
        "/api/v1/ai/generate",
        json={
            "ideological": "科技报国",
            "knowledge": "系统工程",
            "profession": ["航空航天工程"],
        },
        headers=auth(token),
    )

    records = await client.get("/api/v1/ai/records", headers=auth(token))
    assert records.json()["data"]["total"] >= 1


async def test_ask_stream_returns_content(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """问答接口应基于已发布案例流式作答并记录。"""
    token = await _login(client, "student01")
    response = await client.post(
        "/api/v1/ai/ask/case_001",
        json={"question": "这个案例体现了哪些思政元素？"},
        headers=auth(token),
    )

    assert response.status_code == 200
    assert "event: content" in response.text
    assert "event: done" in response.text

    records = await client.get("/api/v1/users/me/ask-records", headers=auth(token))
    assert records.json()["data"]["total"] >= 1
