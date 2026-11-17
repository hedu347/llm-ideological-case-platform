"""接口契约完整性测试。

以 OpenAPI 文档为准，检查设计清单中的路径与方法都已注册。
"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio

EXPECTED: set[tuple[str, str]] = {
    # 账号与权限
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/logout"),
    ("get", "/api/v1/users/me"),
    ("patch", "/api/v1/users/me"),
    ("put", "/api/v1/users/me/password"),
    ("post", "/api/v1/users"),
    ("patch", "/api/v1/users/{user_id}"),
    ("post", "/api/v1/users/{user_id}/reset-password"),
    ("get", "/api/v1/audit-logs"),
    ("get", "/api/v1/users"),
    # 检索、浏览与收藏
    ("get", "/api/v1/cases"),
    ("get", "/api/v1/cases/{case_ref}"),
    ("post", "/api/v1/cases/{case_ref}/favorite"),
    ("delete", "/api/v1/cases/{case_ref}/favorite"),
    ("get", "/api/v1/users/me/favorites"),
    # 案例生产
    ("post", "/api/v1/cases"),
    ("patch", "/api/v1/cases/{case_ref}"),
    ("delete", "/api/v1/cases/{case_ref}"),
    ("post", "/api/v1/cases/{case_ref}/submit"),
    ("post", "/api/v1/cases/parse"),
    ("get", "/api/v1/users/me/cases"),
    ("get", "/api/v1/cases/{case_ref}/review"),
    # AI
    ("post", "/api/v1/ai/generate"),
    ("get", "/api/v1/ai/records"),
    ("get", "/api/v1/ai/records/{record_id}"),
    ("delete", "/api/v1/ai/records/{record_id}"),
    ("post", "/api/v1/ai/ask/{case_ref}"),
    ("get", "/api/v1/users/me/ask-records"),
    # 管理后台
    ("get", "/api/v1/admin/reviews"),
    ("post", "/api/v1/admin/cases/{case_ref}/review"),
    ("get", "/api/v1/admin/cases"),
    ("patch", "/api/v1/admin/cases/{case_ref}"),
    ("delete", "/api/v1/admin/cases/{case_ref}"),
    ("post", "/api/v1/admin/cases/{case_ref}/offline"),
    ("post", "/api/v1/admin/cases/import"),
    ("get", "/api/v1/admin/cases/export"),
    ("get", "/api/v1/admin/tags"),
    ("post", "/api/v1/admin/tags"),
    ("patch", "/api/v1/admin/tags/{tag_id}"),
    ("delete", "/api/v1/admin/tags/{tag_id}"),
    ("get", "/api/v1/admin/professions"),
    ("post", "/api/v1/admin/professions"),
    ("patch", "/api/v1/admin/professions/{profession_id}"),
    ("get", "/api/v1/admin/statistics/home"),
    # 首页
    ("get", "/api/v1/home/index-data"),
}


async def test_openapi_contains_all_contract_paths(
    client: httpx.AsyncClient,
) -> None:
    """设计清单中的每个路径与方法都必须出现在 OpenAPI 中。"""
    document = (await client.get("/openapi.json")).json()
    paths = document["paths"]

    missing = [
        (method, path)
        for method, path in EXPECTED
        if path not in paths or method not in paths[path]
    ]
    assert not missing, missing
