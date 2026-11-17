"""案例检索、详情与收藏的集成测试。"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "123456"},
    )
    return response.json()["data"]["token"]


async def test_public_list_only_returns_published(
    client: httpx.AsyncClient,
    seeded_db,
) -> None:
    """公开列表不得泄露草稿、待审核等状态。"""
    response = await client.get("/api/v1/cases")
    records = response.json()["data"]["records"]

    assert records
    assert all(item["review_status"] == "已发布" for item in records)


async def test_keyword_and_tag_filter(
    client: httpx.AsyncClient,
    seeded_db,
) -> None:
    """关键词与思政标签都应能命中案例。"""
    by_keyword = await client.get("/api/v1/cases", params={"keyword": "钱学森"})
    assert any("钱学森" in item["title"] for item in by_keyword.json()["data"]["records"])

    by_tag = await client.get("/api/v1/cases", params={"tag": "文化自信"})
    assert by_tag.json()["data"]["total"] >= 1


async def test_detail_of_draft_is_not_visible_to_student(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """学生访问草稿详情应返回 404。"""
    token = await _login(client, "student01")
    response = await client.get("/api/v1/cases/case_017", headers=auth(token))
    assert response.status_code == 404


async def test_pagination_bounds(
    client: httpx.AsyncClient,
    seeded_db,
) -> None:
    """超出总页数返回空列表，size 上限截断为 100。"""
    response = await client.get("/api/v1/cases", params={"page": 999, "size": 999})
    data = response.json()["data"]

    assert data["records"] == []
    assert data["size"] == 100


async def test_favorite_is_idempotent(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """重复收藏同一案例只保留一条记录。"""
    token = await _login(client, "student02")

    await client.post("/api/v1/cases/case_001/favorite", headers=auth(token))
    await client.post("/api/v1/cases/case_001/favorite", headers=auth(token))

    favorites = await client.get("/api/v1/users/me/favorites", headers=auth(token))
    assert favorites.json()["data"]["total"] == 1
