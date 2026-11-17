"""AI 生成、问答与记录接口。"""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.deps import CurrentUser, SessionDep, require_roles
from app.core.response import fail, ok
from app.core.timeutil import now_text, today_compact
from app.models import AiRecord, AskRecord, Case, User
from app.services import ai as ai_service
from app.services.cases import case_to_public, find_case, normalize_page

router = APIRouter(tags=["AI"])
TeacherUser = Annotated[User, Depends(require_roles("teacher", "admin"))]


def _sse(event: str, data: dict[str, Any]) -> str:
    """序列化一条 SSE 事件。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _streaming_response(events) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _reference_cases(session: Any, ideological: str) -> list[dict[str, Any]]:
    """从已发布案例中取最多三条相关案例作为参考。"""
    statement = select(Case).where(Case.review_status == "已发布")
    if ideological:
        statement = statement.where(
            Case.ideological_elements.contains([ideological])
        )
    cases = (await session.execute(statement.limit(3))).scalars().all()
    if not cases:
        cases = (
            await session.execute(
                select(Case).where(Case.review_status == "已发布").limit(3)
            )
        ).scalars().all()
    return [
        {
            "id": case.case_no,
            "title": case.title,
            "category": case.category,
            "sourceType": case.source_type,
        }
        for case in cases
    ]


class GenerateRequest(BaseModel):
    """生成请求。"""

    ideological: str
    knowledge: str
    profession: list[str] = []


@router.post("/ai/generate", summary="AI 案例生成（SSE）")
async def generate_case(
    payload: GenerateRequest,
    user: TeacherUser,
    session: SessionDep,
) -> StreamingResponse:
    """多稿生成、逐稿评分并流式返回最优稿正文。"""
    references = await _reference_cases(session, payload.ideological)

    async def on_done(best, text: str, drafts) -> int | None:
        record = AiRecord(
            user_id=user.id,
            category=best.case["category"],
            topic=payload.knowledge,
            ideological_direction=payload.ideological,
            profession=best.case["profession"],
            content_preview=text[:120] + "……",
            content=text,
            publish_date=today_compact(),
            version="V1.0",
            evaluation=best.evaluation,
            draft_count=len(drafts),
            drafts=[
                {"index": index, "totalScore": draft.evaluation["totalScore"]}
                for index, draft in enumerate(drafts, start=1)
            ],
            generated_data=best.case,
            create_time=now_text(),
        )
        session.add(record)
        await session.flush()
        await session.commit()
        return record.id

    async def event_stream():
        async for event, data in ai_service.stream_generate(
            payload.model_dump(),
            references=references,
            on_done=on_done,
        ):
            yield _sse(event, data)

    return _streaming_response(event_stream())


class AskRequest(BaseModel):
    """问答请求。``caseContext`` 用于尚未入库的生成内容。"""

    question: str
    caseContext: dict[str, Any] | None = None


@router.post("/ai/ask/{case_ref}", summary="AI 智能问答（SSE）")
async def ask_case(
    case_ref: str,
    payload: AskRequest,
    user: CurrentUser,
    session: SessionDep,
) -> Any:
    """基于案例上下文流式作答；``draft`` 表示使用请求体中的上下文。"""
    case_context = dict(payload.caseContext or {})
    case = None

    if case_ref != "draft":
        case = await find_case(session, case_ref)
        if case is None:
            raise HTTPException(status_code=404, detail="案例不存在")
        case_context = {**case_to_public(case), **case_context}

    if not case_context:
        return fail(400, "缺少案例上下文")

    async def on_done(answer: str) -> int | None:
        if case is None:
            return None
        record = AskRecord(
            user_id=user.id,
            case_no=case.case_no,
            case_title=case.title,
            question=payload.question,
            answer=answer,
            create_time=now_text(),
        )
        session.add(record)
        await session.flush()
        await session.commit()
        return record.id

    async def event_stream():
        async for event, data in ai_service.stream_ask(
            case_context,
            payload.question,
            on_done=on_done,
        ):
            yield _sse(event, data)

    return _streaming_response(event_stream())


def ai_record_to_dict(record: AiRecord) -> dict[str, Any]:
    """返回前端生成记录页消费的形状。"""
    return {
        "id": record.id,
        "username": "",
        "createTime": record.create_time,
        "category": record.category,
        "topic": record.topic,
        "ideological_direction": record.ideological_direction,
        "profession": record.profession or [],
        "contentPreview": record.content_preview,
        "content": record.content,
        "publish_date": record.publish_date,
        "version": record.version,
        "evaluation": record.evaluation,
        "draftCount": record.draft_count,
        "drafts": record.drafts,
        "generatedData": record.generated_data,
    }


@router.get("/ai/records", summary="本人生成记录")
async def list_ai_records(
    user: TeacherUser,
    session: SessionDep,
    page: int = 1,
    size: int = 10,
) -> dict[str, object]:
    """按生成时间倒序返回本人记录。"""
    page, size = normalize_page(page, size)
    statement = select(AiRecord).where(AiRecord.user_id == user.id)
    total = (
        await session.execute(select(func.count()).select_from(statement.subquery()))
    ).scalar_one()
    records = (
        await session.execute(
            statement.order_by(AiRecord.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return ok(
        {
            "total": total,
            "records": [ai_record_to_dict(record) for record in records],
            "page": page,
            "size": size,
        }
    )


@router.get("/ai/records/{record_id}", summary="生成记录详情")
async def get_ai_record(
    record_id: int,
    user: TeacherUser,
    session: SessionDep,
) -> dict[str, object]:
    """仅本人可查看。"""
    record = await session.get(AiRecord, record_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return ok(ai_record_to_dict(record))


@router.delete("/ai/records/{record_id}", summary="删除生成记录")
async def delete_ai_record(
    record_id: int,
    user: TeacherUser,
    session: SessionDep,
) -> dict[str, object]:
    """仅本人可删除。"""
    record = await session.get(AiRecord, record_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")

    await session.delete(record)
    await session.commit()
    return ok(None, "删除成功")


@router.get("/users/me/ask-records", summary="本人问答记录")
async def list_ask_records(
    user: CurrentUser,
    session: SessionDep,
    page: int = 1,
    size: int = 10,
) -> dict[str, object]:
    """按时间倒序返回本人问答记录。"""
    page, size = normalize_page(page, size)
    statement = select(AskRecord).where(AskRecord.user_id == user.id)
    total = (
        await session.execute(select(func.count()).select_from(statement.subquery()))
    ).scalar_one()
    records = (
        await session.execute(
            statement.order_by(AskRecord.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return ok(
        {
            "total": total,
            "records": [
                {
                    "id": record.id,
                    "username": "",
                    "caseId": record.case_no,
                    "caseTitle": record.case_title,
                    "question": record.question,
                    "answer": record.answer,
                    "createTime": record.create_time,
                }
                for record in records
            ],
            "page": page,
            "size": size,
        }
    )
