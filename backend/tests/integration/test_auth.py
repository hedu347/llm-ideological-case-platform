"""认证、用户管理与权限的集成测试。"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client: httpx.AsyncClient, username: str, password: str = "123456") -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return response.json()["data"]["token"]


async def test_login_ok_returns_token_and_user(
    client: httpx.AsyncClient,
    seeded_db,
) -> None:
    """正确账号密码应返回令牌与角色。"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "teacher01", "password": "123456"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["role"] == "teacher"
    assert body["data"]["user"]["nickName"] == "李老师"


async def test_login_wrong_password_is_business_error_with_http_200(
    client: httpx.AsyncClient,
    seeded_db,
) -> None:
    """登录失败必须是 HTTP 200 + 非零 code，前端才能弹提示而不跳转。"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "teacher01", "password": "bad"},
    )

    assert response.status_code == 200
    assert response.json()["code"] == 400


async def test_frozen_account_cannot_use_old_token(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """账号冻结后，已签发令牌应立即失效。"""
    student_token = await _login(client, "student01")
    admin_token = await _login(client, "admin01")

    listing = await client.get(
        "/api/v1/users",
        params={"keyword": "student01"},
        headers=auth(admin_token),
    )
    student_id = listing.json()["data"]["records"][0]["id"]

    update = await client.patch(
        f"/api/v1/users/{student_id}",
        json={"status": 1},
        headers=auth(admin_token),
    )
    assert update.json()["code"] == 0

    me = await client.get("/api/v1/users/me", headers=auth(student_token))
    assert me.status_code == 403


async def test_teacher_cannot_access_admin_users(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """教师访问管理员接口应返回 403。"""
    teacher_token = await _login(client, "teacher01")
    response = await client.get("/api/v1/users", headers=auth(teacher_token))
    assert response.status_code == 403


async def test_admin_can_create_user_and_reset_password(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """管理员创建账号并重置密码后，新账号可登录。"""
    admin_token = await _login(client, "admin01")

    created = await client.post(
        "/api/v1/users",
        json={"username": "new_teacher", "nickName": "新老师", "role": "teacher"},
        headers=auth(admin_token),
    )
    assert created.json()["code"] == 0
    user_id = created.json()["data"]["id"]

    reset = await client.post(
        f"/api/v1/users/{user_id}/reset-password",
        headers=auth(admin_token),
    )
    assert reset.json()["code"] == 0

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "new_teacher", "password": "123456"},
    )
    assert login.json()["code"] == 0
