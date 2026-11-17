"""平台统计聚合。"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiRecord, Case, Profession, Tag, User


async def _count(session: AsyncSession, statement) -> int:
    """统计子查询行数。"""
    return (
        await session.execute(select(func.count()).select_from(statement.subquery()))
    ).scalar_one()


async def build_statistics(session: AsyncSession) -> dict[str, object]:
    """构造管理后台统计页所需数据。"""
    today_prefix = datetime.now().strftime("%Y-%m-%d")

    category_rows = (
        await session.execute(
            select(Case.category, func.count())
            .where(Case.review_status == "已发布")
            .group_by(Case.category)
        )
    ).all()
    source_rows = (
        await session.execute(
            select(Case.source_type, func.count())
            .where(Case.review_status == "已发布")
            .group_by(Case.source_type)
        )
    ).all()

    return {
        "totalCases": await _count(session, select(Case)),
        "collectedCaseCount": await _count(
            session, select(Case).where(Case.review_status == "已发布")
        ),
        "totalUsers": await _count(session, select(User)),
        "todayAiCount": await _count(
            session,
            select(AiRecord).where(AiRecord.create_time.like(f"{today_prefix}%")),
        ),
        "pendingReviewCount": await _count(
            session, select(Case).where(Case.review_status == "待审核")
        ),
        "categoryDistribution": [
            {"name": name or "未分类", "count": count} for name, count in category_rows
        ],
        "sourceDistribution": [
            {"name": name or "未知", "value": count} for name, count in source_rows
        ],
    }


async def build_home_index(session: AsyncSession) -> dict[str, int]:
    """构造首页平台规模数据。"""
    return {
        "totalCases": await _count(session, select(Case)),
        "collectedCaseCount": await _count(
            session, select(Case).where(Case.review_status == "已发布")
        ),
        "totalProfessions": await _count(session, select(Profession)),
        "totalTags": await _count(session, select(Tag)),
        "totalAiGenerated": await _count(session, select(AiRecord)),
    }
