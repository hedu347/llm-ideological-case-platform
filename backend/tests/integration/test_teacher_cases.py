"""教师案例生产与提交审核的集成测试。"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "123456"},
    )
    return response.json()["data"]["token"]


async def test_teacher_creates_draft_and_submits(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """新建草稿后提交应转为待审核。"""
    token = await _login(client, "teacher01")

    created = await client.post(
        "/api/v1/cases",
        json={"title": "新案例", "category": "行业案例"},
        headers=auth(token),
    )
    body = created.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "草稿"
    case_id = body["data"]["id"]

    submitted = await client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers=auth(token),
    )
    assert submitted.json()["data"]["status"] == "待审核"


async def test_teacher_cannot_edit_other_teacher_case(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """教师编辑他人案例应被拒绝。"""
    token = await _login(client, "teacher01")
    response = await client.patch(
        "/api/v1/cases/case_013",
        json={"title": "越权修改"},
        headers=auth(token),
    )
    assert response.status_code in (403, 404)


async def test_only_draft_can_be_deleted(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """非草稿状态的案例不可删除。"""
    token = await _login(client, "teacher01")
    response = await client.delete("/api/v1/cases/case_018", headers=auth(token))
    assert response.json()["code"] == 400


async def test_student_cannot_create_case(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """学生没有案例生产权限。"""
    token = await _login(client, "student01")
    response = await client.post(
        "/api/v1/cases",
        json={"title": "学生案例", "category": "行业案例"},
        headers=auth(token),
    )
    assert response.status_code == 403


async def test_parse_returns_candidate_fields(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """上传文本应返回可回填的候选字段。"""
    token = await _login(client, "teacher01")
    response = await client.post(
        "/api/v1/cases/parse",
        json={"text": "第一行是标题\n这是背景段落。\n这是过程段落。\n这是结果段落。"},
        headers=auth(token),
    )
    data = response.json()["data"]
    assert data["title"]
    assert "background" in data
