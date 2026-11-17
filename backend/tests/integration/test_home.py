"""首页平台数据接口测试。"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def test_home_index_returns_all_fields(
    client: httpx.AsyncClient,
    seeded_db,
) -> None:
    """首页数据必须包含前端展示所需的全部字段。"""
    response = await client.get("/api/v1/home/index-data")
    data = response.json()["data"]

    assert set(data) == {
        "totalCases",
        "collectedCaseCount",
        "totalProfessions",
        "totalTags",
        "totalAiGenerated",
    }
    assert data["totalCases"] >= 12
