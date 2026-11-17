"""管理后台：审核、案例维护、字典与统计接口。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.v1.teacher_cases import (
    CasePayload,
    FIELD_MAP,
    case_to_teacher,
)
from app.core.deps import CurrentUser, SessionDep, require_roles
from app.core.response import fail, ok
from app.core.timeutil import now_text, today_compact
from app.models import Case, Profession, Tag, User
from app.services.audit import add_audit
from app.services.cases import find_case, next_case_no, normalize_page
from app.services.stats import build_statistics

router = APIRouter(tags=["管理后台"])
AdminUser = Annotated[User, Depends(require_roles("admin"))]

VALID_REVIEW_STATUSES = {"已发布", "需补充", "审核驳回"}
VALID_CASE_STATUSES = {"草稿", "待审核", "需补充", "审核驳回", "已发布", "已下线"}


class AdminCasePayload(CasePayload):
    """管理员维护案例时可额外调整状态。"""

    review_status: str | None = None


@router.get("/admin/reviews", summary="审核队列")
async def list_reviews(
    admin: AdminUser,
    session: SessionDep,
    page: int = 1,
    size: int = 10,
    status: str | None = None,
) -> dict[str, object]:
    """返回待审核与历史提交记录，供管理页筛选。"""
    page, size = normalize_page(page, size)
    statement = select(Case)
    if status:
        statement = statement.where(Case.review_status == status)

    total = (
        await session.execute(select(func.count()).select_from(statement.subquery()))
    ).scalar_one()
    cases = (
        await session.execute(
            statement.order_by(Case.submit_time.desc(), Case.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return ok(
        {
            "total": total,
            "records": [case_to_teacher(case) for case in cases],
            "page": page,
            "size": size,
        }
    )


class ReviewRequest(BaseModel):
    """审核请求，兼容前端 rejectReason 字段名。"""

    status: str
    opinion: str = ""
    rejectReason: str = ""


@router.post("/admin/cases/{case_ref}/review", summary="审核案例")
async def review_case(
    case_ref: str,
    payload: ReviewRequest,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """通过、需补充或驳回，并记录审核意见。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")
    if payload.status not in VALID_REVIEW_STATUSES:
        return fail(400, "审核状态不合法")

    case.review_status = payload.status
    case.reject_reason = payload.opinion or payload.rejectReason
    case.reviewer_id = admin.id
    case.review_time = now_text()
    case.update_time = now_text()

    action = "审核通过" if payload.status == "已发布" else f"审核{payload.status}"
    add_audit(
        session,
        admin,
        action,
        case.case_no,
        f"{case.title}｜{case.reject_reason or '无意见'}",
    )
    await session.commit()
    return ok(
        {"caseSubmitId": case.id, "status": case.review_status},
        "操作成功",
    )


@router.get("/admin/cases", summary="全量案例查询")
async def list_all_cases(
    admin: AdminUser,
    session: SessionDep,
    page: int = 1,
    size: int = 10,
    status: str | None = None,
    category: str | None = None,
    keyword: str = "",
) -> dict[str, object]:
    """管理员查看所有状态的案例。"""
    page, size = normalize_page(page, size)
    statement = select(Case)
    if status:
        statement = statement.where(Case.review_status == status)
    if category:
        statement = statement.where(Case.category == category)
    if keyword:
        like = f"%{keyword}%"
        statement = statement.where(Case.title.ilike(like))

    total = (
        await session.execute(select(func.count()).select_from(statement.subquery()))
    ).scalar_one()
    cases = (
        await session.execute(
            statement.order_by(Case.update_time.desc(), Case.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return ok(
        {
            "total": total,
            "records": [case_to_teacher(case) for case in cases],
            "page": page,
            "size": size,
        }
    )


@router.patch("/admin/cases/{case_ref}", summary="维护案例")
async def update_case(
    case_ref: str,
    payload: AdminCasePayload,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """管理员可编辑任意状态的案例字段，包括重新发布。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")

    if payload.review_status is not None:
        if payload.review_status not in VALID_CASE_STATUSES:
            return fail(400, "案例状态不合法")
        case.review_status = payload.review_status

    for field, column in FIELD_MAP.items():
        value = getattr(payload, field)
        if value is not None:
            setattr(case, column, value)
    case.update_time = now_text()
    await session.commit()
    return ok(case_to_teacher(case), "更新成功")


@router.delete("/admin/cases/{case_ref}", summary="删除案例")
async def delete_case(
    case_ref: str,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """管理员删除案例。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")

    await session.delete(case)
    await session.commit()
    return ok(None, "删除成功")


class OfflineRequest(BaseModel):
    reason: str = ""


@router.post("/admin/cases/{case_ref}/offline", summary="下线案例")
async def offline_case(
    case_ref: str,
    payload: OfflineRequest,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """仅已发布案例可下线，下线后停止对外展示。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")
    if case.review_status != "已发布":
        return fail(400, "仅“已发布”案例可下线")

    case.review_status = "已下线"
    case.offline_reason = payload.reason
    case.update_time = now_text()
    add_audit(
        session,
        admin,
        "下线案例",
        case.case_no,
        f"下线原因：{payload.reason or '未填写'}",
    )
    await session.commit()
    return ok(case_to_teacher(case), "已下线")


@router.post("/admin/cases/import", summary="批量导入案例")
async def import_cases(
    rows: list[CasePayload],
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """按字段规范批量导入，缺标题或分类的行记为失败。"""
    success = 0
    failed: list[str] = []

    for row in rows:
        if not (row.title and row.category):
            failed.append(row.title or "(未命名)")
            continue

        case = Case(
            case_no=await next_case_no(session),
            title=row.title or "",
            category=row.category or "",
            source=row.source or "批量导入",
            source_url=row.source_url or "",
            source_type="人工导入",
            publish_date=row.publish_date or today_compact(),
            collect_date=today_compact(),
            version=row.version or "V1.1",
            review_status="已发布",
            background=row.background or "",
            content=row.content or "",
            process=row.process or "",
            result=row.result or "",
            profession=row.profession or [],
            keywords=row.keywords or [],
            professional_knowledge=row.professional_knowledge or [],
            ideological_elements=row.ideological_elements or [],
            teaching_value=row.teaching_value or "",
            submitter_name="批量导入",
            create_time=today_compact(),
        )
        session.add(case)
        await session.flush()
        success += 1

    await session.commit()
    return ok(
        {"success": success, "fail": failed},
        f"导入完成：成功 {success} 条",
    )


def _csv_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    if any(char in text for char in (",", '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


@router.get("/admin/cases/export", summary="导出案例")
async def export_cases(admin: AdminUser, session: SessionDep) -> Response:
    """导出已发布案例为 CSV，带 UTF-8 BOM 以便 Excel 正确打开。"""
    cases = (
        await session.execute(
            select(Case).where(Case.review_status == "已发布").order_by(Case.id)
        )
    ).scalars().all()

    header = [
        "id",
        "title",
        "source",
        "publish_date",
        "category",
        "review_status",
        "profession",
        "keywords",
        "ideological_elements",
    ]
    lines = [",".join(header)]
    for case in cases:
        lines.append(
            ",".join(
                [
                    _csv_cell(case.case_no),
                    _csv_cell(case.title),
                    _csv_cell(case.source),
                    _csv_cell(case.publish_date),
                    _csv_cell(case.category),
                    _csv_cell(case.review_status),
                    _csv_cell("|".join(case.profession or [])),
                    _csv_cell("|".join(case.keywords or [])),
                    _csv_cell("|".join(case.ideological_elements or [])),
                ]
            )
        )

    content = "﻿" + "\n".join(lines)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="cases_{today_compact()}.csv"'
        },
    )


def tag_record(tag: Tag) -> dict[str, object]:
    return {
        "id": tag.id,
        "name": tag.name,
        "useCount": tag.use_count,
        "status": tag.status,
        "createTime": tag.create_time,
    }


@router.get("/admin/tags", summary="思政标签列表")
async def list_tags(user: CurrentUser, session: SessionDep) -> dict[str, object]:
    """标签查询对全部登录用户开放。"""
    tags = (await session.execute(select(Tag).order_by(Tag.id))).scalars().all()
    return ok([tag_record(tag) for tag in tags])


class TagPayload(BaseModel):
    name: str | None = None
    status: int | None = None


@router.post("/admin/tags", summary="新增思政标签")
async def create_tag(
    payload: TagPayload,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """新增标签，名称重复时拒绝。"""
    if not payload.name:
        return fail(400, "请填写标签名称")
    exists = (
        await session.execute(select(Tag).where(Tag.name == payload.name))
    ).scalar_one_or_none()
    if exists is not None:
        return fail(400, "该标签已存在")

    tag = Tag(
        name=payload.name,
        use_count=0,
        status=1,
        create_time=today_compact(),
    )
    session.add(tag)
    await session.commit()
    return ok(tag_record(tag), "新增成功")


@router.patch("/admin/tags/{tag_id}", summary="编辑或停用标签")
async def update_tag(
    tag_id: int,
    payload: TagPayload,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """局部更新标签名称或状态。"""
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")

    if payload.name is not None:
        tag.name = payload.name
    if payload.status is not None:
        tag.status = payload.status
    await session.commit()
    return ok(tag_record(tag), "更新成功")


@router.delete("/admin/tags/{tag_id}", summary="删除标签")
async def delete_tag(
    tag_id: int,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """删除标签。"""
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")

    await session.delete(tag)
    await session.commit()
    return ok(None, "删除成功")


def profession_record(profession: Profession) -> dict[str, object]:
    return {
        "id": profession.id,
        "name": profession.name,
        "caseCount": profession.case_count,
        "status": profession.status,
        "createTime": profession.create_time,
    }


@router.get("/admin/professions", summary="专业字典列表")
async def list_professions(
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    """专业查询对全部登录用户开放。"""
    items = (
        await session.execute(select(Profession).order_by(Profession.id))
    ).scalars().all()
    return ok([profession_record(item) for item in items])


class ProfessionPayload(BaseModel):
    name: str | None = None
    status: int | None = None


@router.post("/admin/professions", summary="新增专业")
async def create_profession(
    payload: ProfessionPayload,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """新增专业，名称重复时拒绝。"""
    if not payload.name:
        return fail(400, "请填写专业名称")
    exists = (
        await session.execute(
            select(Profession).where(Profession.name == payload.name)
        )
    ).scalar_one_or_none()
    if exists is not None:
        return fail(400, "该专业已存在")

    item = Profession(
        name=payload.name,
        case_count=0,
        status=1,
        create_time=today_compact(),
    )
    session.add(item)
    await session.commit()
    return ok(profession_record(item), "新增成功")


@router.patch("/admin/professions/{profession_id}", summary="编辑或停用专业")
async def update_profession(
    profession_id: int,
    payload: ProfessionPayload,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """局部更新专业名称或状态。"""
    item = await session.get(Profession, profession_id)
    if item is None:
        raise HTTPException(status_code=404, detail="专业不存在")

    if payload.name is not None:
        item.name = payload.name
    if payload.status is not None:
        item.status = payload.status
    await session.commit()
    return ok(profession_record(item), "更新成功")


@router.get("/admin/statistics/home", summary="平台统计")
async def statistics(admin: AdminUser, session: SessionDep) -> dict[str, object]:
    """返回管理后台统计页所需聚合数据。"""
    return ok(await build_statistics(session))
