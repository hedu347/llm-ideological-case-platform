"""案例检索、详情与收藏接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.core.deps import CurrentUser, SessionDep, get_optional_user
from app.core.response import ok
from app.core.timeutil import now_text
from app.models import Case, Favorite, User
from app.services.cases import (
    case_to_public,
    favorite_case_ids,
    find_case,
    list_cases,
    normalize_page,
)

router = APIRouter(tags=["案例"])

OptionalUser = Annotated[User | None, Depends(get_optional_user)]


@router.get("/cases", summary="检索案例")
async def get_cases(
    session: SessionDep,
    user: OptionalUser,
    keyword: str = "",
    category: str | None = None,
    profession: str | None = None,
    tag: str | None = None,
    page: int = 1,
    size: int = 9,
    sort: str = "new",
    include_all: bool = Query(False, alias="includeAll"),
    status: str | None = None,
) -> dict[str, object]:
    """公开检索默认只返回已发布案例；管理员可传 includeAll 查看全量。"""
    data = await list_cases(
        session,
        keyword=keyword,
        category=category,
        profession=profession,
        tag=tag,
        page=page,
        size=size,
        sort=sort,
        include_all=include_all,
        status=status,
        user=user,
    )
    return ok(data)


@router.get("/cases/{case_ref}", summary="获取案例详情")
async def get_case_detail(
    case_ref: str,
    session: SessionDep,
    user: OptionalUser,
) -> dict[str, object]:
    """已发布案例对全部用户可见；其他状态仅作者与管理员可见。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")

    if case.review_status != "已发布":
        allowed = user is not None and (
            user.role == "admin" or case.author_id == user.id
        )
        if not allowed:
            raise HTTPException(status_code=404, detail="案例不存在")

    favorites = (
        await favorite_case_ids(session, user.id) if user is not None else set()
    )
    return ok(case_to_public(case, case.id in favorites))


@router.post("/cases/{case_ref}/favorite", summary="收藏案例")
async def add_favorite(
    case_ref: str,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    """幂等收藏：已收藏时直接返回成功。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")

    existing = (
        await session.execute(
            select(Favorite).where(
                Favorite.user_id == user.id,
                Favorite.case_id == case.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            Favorite(user_id=user.id, case_id=case.id, create_time=now_text())
        )
        await session.commit()

    return ok({"caseId": case.case_no, "favorited": True}, "收藏成功")


@router.delete("/cases/{case_ref}/favorite", summary="取消收藏")
async def remove_favorite(
    case_ref: str,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    """幂等取消收藏。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")

    existing = (
        await session.execute(
            select(Favorite).where(
                Favorite.user_id == user.id,
                Favorite.case_id == case.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        await session.commit()

    return ok({"caseId": case.case_no, "favorited": False}, "已取消收藏")


@router.get("/users/me/favorites", summary="我的收藏")
async def get_my_favorites(
    user: CurrentUser,
    session: SessionDep,
    page: int = 1,
    size: int = 9,
) -> dict[str, object]:
    """按收藏时间倒序返回本人收藏的已发布案例。"""
    page, size = normalize_page(page, size)
    base = (
        select(Case)
        .join(Favorite, Favorite.case_id == Case.id)
        .where(
            Favorite.user_id == user.id,
            Case.review_status == "已发布",
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    cases = (
        await session.execute(
            base.order_by(Favorite.id.desc()).offset((page - 1) * size).limit(size)
        )
    ).scalars().all()

    return ok(
        {
            "total": total,
            "records": [case_to_public(case, True) for case in cases],
            "page": page,
            "size": size,
        }
    )
