"""AI 生成与问答的流式编排。"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.integrations.llm import builtin
from app.integrations.llm.base import Draft, LLMProvider

ChunkSize = 3


def _chunks(text: str, size: int = ChunkSize) -> list[str]:
    """把文本切成小块，模拟流式输出。"""
    return [text[index : index + size] for index in range(0, len(text), size)]


def compose_text(case: dict[str, Any]) -> str:
    """把结构化案例拼成展示用正文。"""
    knowledge = (case.get("professional_knowledge") or ["专业知识点"])[0]
    return "\n".join(
        [
            f'【案例标题】{case.get("title", "")}',
            "",
            f'【案例背景】{case.get("background", "")}',
            "",
            f'【思政切入点】{"、".join(case.get("ideological_elements") or [])}',
            "",
            "【案例正文】",
            case.get("process", ""),
            "",
            f'【教学成效】{case.get("result", "")}',
            "",
            f"【配套思考题】1. 结合本案例，谈谈你对“{knowledge}”中蕴含思政价值的理解；"
            "2. 请从专业角度分析这一思政导向在同类场景中的迁移应用。",
        ]
    )


async def stream_generate(
    params: dict[str, Any],
    *,
    provider: LLMProvider | None = None,
    references: list[dict[str, Any]] | None = None,
    on_done: Callable[[Draft, str, list[Draft]], Awaitable[int | None]] | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """产出生成过程事件。

    事件顺序与前端消费约定一致：progress → content → references →
    evaluation → done；任何异常都转换为 error 事件，避免连接挂起。
    """
    ideological = params.get("ideological") or ""
    knowledge = params.get("knowledge") or ""
    profession = params.get("profession") or []

    if not ideological or not knowledge:
        yield ("error", {"code": 400, "message": "请选择思政方向并填写知识点"})
        return

    active = provider or builtin
    try:
        # 模型调用是同步阻塞的，放到线程里避免卡住事件循环。
        drafts = await asyncio.to_thread(
            active.generate, ideological, knowledge, profession
        )
    except Exception:
        yield ("error", {"code": 6000, "message": "模型暂不可用"})
        return

    total = len(drafts)
    for index in range(1, total + 1):
        yield (
            "progress",
            {
                "stage": "drafting",
                "index": index,
                "total": total,
                "message": f"正在生成候选案例（{index}/{total}）…",
            },
        )

    yield (
        "progress",
        {
            "stage": "evaluating",
            "index": total,
            "total": total,
            "message": "AI 辅助评价中，正在择优…",
        },
    )

    best = max(drafts, key=lambda item: item.evaluation["totalScore"])
    text = compose_text(best.case)

    for chunk in _chunks(text):
        yield ("content", {"delta": chunk})

    if references:
        yield ("references", {"items": references})
    yield ("evaluation", best.evaluation)

    record_id = await on_done(best, text, drafts) if on_done is not None else None
    yield (
        "done",
        {
            "record_id": record_id,
            "data": best.case,
            "content": text,
            "evaluation": best.evaluation,
            "drafts": [
                {"index": index, "totalScore": draft.evaluation["totalScore"]}
                for index, draft in enumerate(drafts, start=1)
            ],
            "references": references or [],
        },
    )


async def stream_ask(
    case_context: dict[str, Any],
    question: str,
    *,
    provider: LLMProvider | None = None,
    on_done: Callable[[str], Awaitable[int | None]] | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """产出问答流式事件。"""
    if not question.strip():
        yield ("error", {"code": 400, "message": "请输入问题"})
        return

    active = provider or builtin
    try:
        answer = await asyncio.to_thread(active.ask, case_context, question)
    except Exception:
        yield ("error", {"code": 6001, "message": "回答生成失败"})
        return

    for chunk in _chunks(answer):
        yield ("content", {"delta": chunk})

    record_id = await on_done(answer) if on_done is not None else None
    yield ("done", {"record_id": record_id, "answer": answer})
