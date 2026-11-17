"""种子数据集成测试。

运行前需要 PostgreSQL 与测试库，使用 ``--run-integration`` 启用。
"""

import pytest
from sqlalchemy import func, select

from app.db.seed import seed
from app.models import Case, User

pytestmark = pytest.mark.asyncio


async def test_seed_is_idempotent(db_session) -> None:
    """重复执行种子不应产生重复用户或案例。"""
    await seed(db_session)
    await db_session.commit()
    await seed(db_session)
    await db_session.commit()

    user_count = (
        await db_session.execute(select(func.count()).select_from(User))
    ).scalar_one()
    case_count = (
        await db_session.execute(select(func.count()).select_from(Case))
    ).scalar_one()

    assert user_count == 8
    assert case_count >= 12


async def test_seed_contains_all_case_statuses(db_session) -> None:
    """种子应覆盖已发布、待审核、草稿等演示所需状态。"""
    await seed(db_session)
    await db_session.commit()

    statuses = set(
        (await db_session.execute(select(Case.review_status))).scalars().all()
    )
    assert {"已发布", "待审核", "草稿", "审核驳回", "已下线"} <= statuses
