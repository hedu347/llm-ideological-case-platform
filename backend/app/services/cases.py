"""案例查询、序列化与收藏辅助逻辑。"""

from typing import Any

from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, Favorite, User


def normalize_page(page: int, size: int) -> tuple[int, int]:
    """把分页参数收敛到合法范围。"""
    return max(1, int(page)), min(max(1, int(size)), 100)


def case_to_public(case: Case, is_favorite: bool = False) -> dict[str, Any]:
    """把案例模型转换为前端消费的形状。

    对外 ``id`` 使用 ``case_no``，因为前端列表项直接把 ``id`` 传给详情、
    收藏等接口；内部整数主键不暴露。
    """
    return {
        "id": case.case_no,
        "case_no": case.case_no,
        "title": case.title,
        "source": case.source,
        "source_url": case.source_url,
        "sourceType": case.source_type,
        "publish_date": case.publish_date,
        "collect_date": case.collect_date,
        "version": case.version,
        "category": case.category,
        "review_status": case.review_status,
        "background": case.background,
        "content": case.content,
        "process": case.process,
        "result": case.result,
        "profession": case.profession or [],
        "keywords": case.keywords or [],
        "professional_knowledge": case.professional_knowledge or [],
        "ideological_elements": case.ideological_elements or [],
        "teaching_value": case.teaching_value,
        "views": case.views,
        "createTime": case.create_time,
        "submitterName": case.submitter_name,
        "isFavorite": is_favorite,
    }


async def favorite_case_ids(session: AsyncSession, user_id: int) -> set[int]:
    """返回用户收藏的案例主键集合。"""
    rows = await session.execute(
        select(Favorite.case_id).where(Favorite.user_id == user_id)
    )
    return set(rows.scalars().all())


async def find_case(session: AsyncSession, case_ref: str) -> Case | None:
    """按对外编号或内部主键查找案例。"""
    reference = str(case_ref)
    if reference.isdigit():
        case = await session.get(Case, int(reference))
        if case is not None:
            return case
    return (
        await session.execute(select(Case).where(Case.case_no == reference))
    ).scalar_one_or_none()


async def next_case_no(session: AsyncSession) -> str:
    """按现有最大编号生成下一个 ``case_xxx``。"""
    values = (await session.execute(select(Case.case_no))).scalars().all()
    maximum = 0
    for value in values:
        if value.startswith("case_") and value[5:].isdigit():
            maximum = max(maximum, int(value[5:]))
    return f"case_{maximum + 1:03d}"


async def list_cases(
    session: AsyncSession,
    *,
    keyword: str = "",
    category: str | None = None,
    profession: str | None = None,
    tag: str | None = None,
    page: int = 1,
    size: int = 9,
    sort: str = "new",
    include_all: bool = False,
    status: str | None = None,
    user: User | None = None,
) -> dict[str, Any]:
    """按条件检索案例并分页。"""
    page, size = normalize_page(page, size)
    is_admin = user is not None and user.role == "admin"

    statement = select(Case)
    if include_all and is_admin:
        if status:
            statement = statement.where(Case.review_status == status)
    else:
        statement = statement.where(Case.review_status == "已发布")

    if keyword:
        like = f"%{keyword}%"
        statement = statement.where(
            Case.title.ilike(like)
            | cast(Case.keywords, Text).ilike(like)
            | cast(Case.profession, Text).ilike(like)
            | Case.teaching_value.ilike(like)
            | Case.content.ilike(like)
        )
    if category:
        statement = statement.where(Case.category == category)
    if profession:
        statement = statement.where(Case.profession.contains([profession]))
    if tag:
        statement = statement.where(Case.ideological_elements.contains([tag]))

    statement = _apply_sort(statement, sort)

    total = (
        await session.execute(select(func.count()).select_from(statement.subquery()))
    ).scalar_one()
    cases = (
        await session.execute(
            statement.offset((page - 1) * size).limit(size)
        )
    ).scalars().all()

    favorites: set[int] = set()
    if user is not None:
        favorites = await favorite_case_ids(session, user.id)

    return {
        "total": total,
        "records": [case_to_public(case, case.id in favorites) for case in cases],
        "page": page,
        "size": size,
    }


def _apply_sort(statement: Any, sort: str) -> Any:
    """解析排序参数；只接受白名单字段。"""
    if sort == "views":
        return statement.order_by(Case.views.desc(), Case.publish_date.desc())
    if sort and "," in sort:
        field, _, direction = sort.partition(",")
        column = {"publish_date": Case.publish_date, "views": Case.views}.get(field)
        if column is not None:
            ordering = column.desc() if direction.strip() == "desc" else column.asc()
            return statement.order_by(ordering)
    return statement.order_by(Case.publish_date.desc(), Case.id.desc())
