"""管理后台审核、字典与统计的集成测试。"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "123456"},
    )
    return response.json()["data"]["token"]


async def _review_target(client: httpx.AsyncClient, admin_token: str, case_no: str) -> dict:
    listing = await client.get(
        "/api/v1/admin/reviews",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return next(
        item for item in listing.json()["data"]["records"] if item["case_no"] == case_no
    )


async def test_approve_moves_case_to_published_and_public_list(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """审核通过后案例应出现在公开列表。"""
    admin = await _login(client, "admin01")
    target = await _review_target(client, admin, "case_013")

    result = await client.post(
        f"/api/v1/admin/cases/{target['id']}/review",
        json={"status": "已发布", "opinion": ""},
        headers=auth(admin),
    )
    assert result.json()["code"] == 0

    public = await client.get("/api/v1/cases", params={"keyword": "区块链"})
    assert public.json()["data"]["total"] >= 1


async def test_reject_records_opinion_visible_to_author(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """驳回意见应能被案例作者看到。"""
    admin = await _login(client, "admin01")
    author = await _login(client, "teacher02")
    target = await _review_target(client, admin, "case_013")

    await client.post(
        f"/api/v1/admin/cases/{target['id']}/review",
        json={"status": "审核驳回", "opinion": "内容不足"},
        headers=auth(admin),
    )

    opinion = await client.get(
        f"/api/v1/cases/{target['id']}/review",
        headers=auth(author),
    )
    assert opinion.json()["data"]["opinion"] == "内容不足"


async def test_offline_only_published(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """已发布案例可下线并记录原因。"""
    admin = await _login(client, "admin01")
    response = await client.post(
        "/api/v1/admin/cases/case_001/offline",
        json={"reason": "链接失效"},
        headers=auth(admin),
    )
    assert response.json()["data"]["status"] == "已下线"


async def test_student_blocked_from_admin(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """学生访问管理接口应返回 403。"""
    student = await _login(client, "student01")
    response = await client.get("/api/v1/admin/reviews", headers=auth(student))
    assert response.status_code == 403


async def test_tags_crud(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """标签可新增、修改状态并删除。"""
    admin = await _login(client, "admin01")

    created = await client.post(
        "/api/v1/admin/tags",
        json={"name": "新标签"},
        headers=auth(admin),
    )
    assert created.json()["code"] == 0
    tag_id = created.json()["data"]["id"]

    updated = await client.patch(
        f"/api/v1/admin/tags/{tag_id}",
        json={"status": 0},
        headers=auth(admin),
    )
    assert updated.json()["data"]["status"] == 0

    deleted = await client.delete(
        f"/api/v1/admin/tags/{tag_id}",
        headers=auth(admin),
    )
    assert deleted.json()["code"] == 0


async def test_statistics_fields(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """统计数据应包含前端图表所需字段。"""
    admin = await _login(client, "admin01")
    response = await client.get("/api/v1/admin/statistics/home", headers=auth(admin))
    data = response.json()["data"]

    assert set(data) >= {
        "totalCases",
        "collectedCaseCount",
        "totalUsers",
        "todayAiCount",
        "pendingReviewCount",
        "categoryDistribution",
        "sourceDistribution",
    }


async def test_offline_case_can_be_republished(
    client: httpx.AsyncClient,
    seeded_db,
    auth,
) -> None:
    """已下线案例应能由管理员重新发布，并重新出现在公开列表。"""
    admin = await _login(client, "admin01")

    # case_016 初始为已下线。
    response = await client.patch(
        "/api/v1/admin/cases/case_016",
        json={"review_status": "已发布"},
        headers=auth(admin),
    )
    assert response.json()["data"]["status"] == "已发布"

    public = await client.get("/api/v1/cases", params={"keyword": "经典教学案例"})
    assert public.json()["data"]["total"] >= 1

