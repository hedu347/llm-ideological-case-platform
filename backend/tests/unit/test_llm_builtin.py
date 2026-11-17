"""AI 内置生成器的单元测试。"""

import pytest

from app.integrations.llm import builtin
from app.services import ai as ai_service


def test_builtin_generates_three_scored_drafts() -> None:
    """内置生成器应产出三稿，每稿都有完整字段和评分。"""
    drafts = builtin.generate("科技报国", "系统工程", ["航空航天工程"])

    assert len(drafts) == 3
    for draft in drafts:
        assert draft.case["title"]
        assert draft.case["background"]
        assert 0 <= draft.evaluation["totalScore"] <= 100


def test_builtin_ask_includes_case_context() -> None:
    """问答应引用当前案例标题，体现基于案例上下文作答。"""
    answer = builtin.ask(
        {"title": "案例A", "background": "背景"},
        "这案例的思政点？",
    )
    assert "案例A" in answer


@pytest.mark.asyncio
async def test_stream_generate_emits_error_event_when_provider_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模型异常时必须发出 error 事件，不能挂起或返回半截内容。"""

    def boom(*args, **kwargs):
        raise RuntimeError("model down")

    monkeypatch.setattr(builtin, "generate", boom)

    events = [
        name
        async for name, _ in ai_service.stream_generate(
            {"ideological": "科技报国", "knowledge": "系统工程", "profession": []}
        )
    ]
    assert "error" in events
