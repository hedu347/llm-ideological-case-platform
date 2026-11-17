"""教师案例生产、提交审核与审核意见查询接口。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.deps import SessionDep, require_roles
from app.core.response import fail, ok
from app.core.timeutil import now_text, today_compact
from app.models import Case, User
from app.services.cases import find_case, next_case_no, normalize_page

router = APIRouter(tags=["案例生产"])
TeacherUser = Annotated[User, Depends(require_roles("teacher", "admin"))]

EDITABLE_STATUSES = {"草稿", "需补充"}


class CasePayload(BaseModel):
    """案例表单字段。新建与局部更新共用。"""

    id: int | None = None
    title: str | None = None
    category: str | None = None
    source: str | None = None
    source_url: str | None = None
    publish_date: str | None = None
    collect_date: str | None = None
    version: str | None = None
    background: str | None = None
    content: str | None = None
    process: str | None = None
    result: str | None = None
    profession: list[str] | None = None
    keywords: list[str] | None = None
    professional_knowledge: list[str] | None = None
    ideological_elements: list[str] | None = None
    teaching_value: str | None = None


FIELD_MAP: dict[str, str] = {
    "title": "title",
    "category": "category",
    "source": "source",
    "source_url": "source_url",
    "publish_date": "publish_date",
    "collect_date": "collect_date",
    "version": "version",
    "background": "background",
    "content": "content",
    "process": "process",
    "result": "result",
    "profession": "profession",
    "keywords": "keywords",
    "professional_knowledge": "professional_knowledge",
    "ideological_elements": "ideological_elements",
    "teaching_value": "teaching_value",
}


def case_to_teacher(case: Case) -> dict[str, Any]:
    """返回教师工作区使用的记录形状，``id`` 为整数主键。"""
    return {
        "id": case.id,
        "case_no": case.case_no,
        "username": "",
        "submitterName": case.submitter_name,
        "title": case.title,
        "source": case.source,
        "source_url": case.source_url,
        "sourceType": case.source_type,
        "publish_date": case.publish_date,
        "collect_date": case.collect_date,
        "version": case.version,
        "category": case.category,
        "status": case.review_status,
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
        "submitTime": case.submit_time,
        "updateTime": case.update_time,
        "rejectReason": case.reject_reason,
    }


def _apply_payload(case: Case, payload: CasePayload) -> None:
    """把非空表单字段写回案例。"""
    for field, column in FIELD_MAP.items():
        value = getattr(payload, field)
        if value is not None:
            setattr(case, column, value)


async def _next_case_no(session: Any) -> str:
    """兼容旧调用，转交服务层实现。"""
    return await next_case_no(session)


@router.post("/cases", summary="新建或保存本人案例草稿")
async def save_case(
    payload: CasePayload,
    user: TeacherUser,
    session: SessionDep,
) -> dict[str, object]:
    """带 id 时更新（等价于 PATCH），否则新建草稿。"""
    if payload.id is not None:
        case = await session.get(Case, payload.id)
        if case is None or case.author_id != user.id:
            raise HTTPException(status_code=404, detail="案例不存在")
        _apply_payload(case, payload)
        case.update_time = now_text()
        await session.commit()
        return ok(case_to_teacher(case), "草稿已保存")

    case = Case(
        case_no=await _next_case_no(session),
        author_id=user.id,
        submitter_name=user.nick_name or user.username,
        source="教师投稿",
        source_type="教师上传",
        review_status="草稿",
        create_time=today_compact(),
        submit_time=now_text(),
        update_time=now_text(),
    )
    _apply_payload(case, payload)
    session.add(case)
    await session.commit()
    return ok(case_to_teacher(case), "草稿已保存")


@router.patch("/cases/{case_ref}", summary="编辑本人草稿或需补充案例")
async def update_case(
    case_ref: str,
    payload: CasePayload,
    user: TeacherUser,
    session: SessionDep,
) -> dict[str, object]:
    """仅作者可编辑，且仅限草稿与需补充状态。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")
    if case.author_id != user.id:
        raise HTTPException(status_code=403, detail="无操作权限")
    if case.review_status not in EDITABLE_STATUSES:
        return fail(400, "当前状态不可编辑")

    _apply_payload(case, payload)
    case.update_time = now_text()
    await session.commit()
    return ok(case_to_teacher(case), "已保存")


@router.delete("/cases/{case_ref}", summary="删除本人草稿")
async def delete_case(
    case_ref: str,
    user: TeacherUser,
    session: SessionDep,
) -> dict[str, object]:
    """仅草稿可删除，已发布内容不可删除。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")
    if case.author_id != user.id:
        raise HTTPException(status_code=403, detail="无操作权限")
    if case.review_status != "草稿":
        return fail(400, "仅「草稿」状态的案例可删除")

    await session.delete(case)
    await session.commit()
    return ok(None, "已删除")


@router.post("/cases/{case_ref}/submit", summary="提交案例审核")
async def submit_case(
    case_ref: str,
    user: TeacherUser,
    session: SessionDep,
) -> dict[str, object]:
    """完整性校验通过后把案例转为待审核。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")
    if case.author_id != user.id:
        raise HTTPException(status_code=403, detail="无操作权限")
    if case.review_status not in EDITABLE_STATUSES:
        return fail(400, "当前状态不可提交审核")
    if not case.title.strip() or not case.category.strip():
        return fail(400, "请填写标题与案例分类")

    case.review_status = "待审核"
    case.submit_time = now_text()
    case.update_time = now_text()
    case.reject_reason = ""
    await session.commit()
    return ok({"submitId": case.id, "status": "待审核"}, "提交成功，等待审核")


class ParseRequest(BaseModel):
    """文本抽取请求。"""

    text: str = ""


@router.post("/cases/parse", summary="上传文本并抽取候选字段")
async def parse_case(payload: ParseRequest, user: TeacherUser) -> dict[str, object]:
    """从纯文本中按行粗略抽取标题、背景、过程与结果。"""
    raw = payload.text.strip()
    if not raw:
        return fail(400, "文件内容为空")

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return ok(
        {
            "title": (lines[0] if lines else "未命名案例")[:30],
            "background": raw[:120],
            "process": raw[120:240],
            "result": raw[240:360],
        },
        "已抽取候选字段，请核对补全",
    )


@router.get("/users/me/cases", summary="本人案例列表")
async def get_my_cases(
    user: TeacherUser,
    session: SessionDep,
    page: int = 1,
    size: int = 10,
    status: str | None = None,
) -> dict[str, object]:
    """返回本人各状态案例，``id`` 为整数主键供前端编辑与删除。"""
    page, size = normalize_page(page, size)
    statement = select(Case).where(Case.author_id == user.id)
    if status:
        statement = statement.where(Case.review_status == status)

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


@router.get("/cases/{case_ref}/review", summary="查看本人案例审核意见")
async def get_review_opinion(
    case_ref: str,
    user: TeacherUser,
    session: SessionDep,
) -> dict[str, object]:
    """仅作者与管理员可查看审核结果。"""
    case = await find_case(session, case_ref)
    if case is None:
        raise HTTPException(status_code=404, detail="案例不存在")
    if case.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无操作权限")

    reviewer = (
        await session.get(User, case.reviewer_id)
        if case.reviewer_id is not None
        else None
    )
    return ok(
        {
            "status": case.review_status,
            "opinion": case.reject_reason,
            "reviewer": reviewer.nick_name if reviewer is not None else "管理员",
            "time": case.review_time or case.update_time or case.submit_time,
        }
    )
