"""OpenAI 兼容（DeepSeek）适配器的单元测试。

通过替换 `_post` 避免真实网络调用，只验证请求构造与响应解析。
"""

import json

import pytest

from app.integrations.llm.openai_compatible import OpenAICompatibleProvider


def _provider(monkeypatch: pytest.MonkeyPatch, content: str) -> OpenAICompatibleProvider:
    provider = OpenAICompatibleProvider(
        base_url="https://api.deepseek.com",
        api_key="test-key",
        model="deepseek-chat",
        timeout_seconds=30,
    )
    monkeypatch.setattr(
        provider,
        "_post",
        lambda payload: {"choices": [{"message": {"content": content}}]},
    )
    return provider


def test_generate_parses_three_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型返回的 JSON 应被解析为三稿候选。"""
    payload = {
        "drafts": [
            {
                "case": {
                    "title": f"案例{i}",
                    "background": "背景",
                    "process": "过程",
                    "result": "结果",
                    "profession": ["软件工程"],
                    "keywords": ["关键词"],
                    "professional_knowledge": ["知识点"],
                    "ideological_elements": ["科技报国"],
                    "teaching_value": "价值",
                    "category": "行业案例",
                },
                "evaluation": {
                    "totalScore": 80 + i,
                    "dimensions": [],
                    "suggestions": [],
                },
            }
            for i in range(3)
        ]
    }
    provider = _provider(monkeypatch, json.dumps(payload, ensure_ascii=False))

    drafts = provider.generate("科技报国", "系统工程", ["软件工程"])

    assert len(drafts) == 3
    assert drafts[0].case["title"] == "案例0"
    assert drafts[2].evaluation["totalScore"] == 82


def test_generate_tolerates_markdown_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型偶尔把 JSON 包在 ```json 代码块里，也要能解析。"""
    raw = '```json\n{"drafts": []}\n```'
    provider = _provider(monkeypatch, raw)

    assert provider.generate("科技报国", "系统工程", []) == []


def test_generate_raises_on_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺少 choices 时应抛出异常，交由上层转为 error 事件。"""
    monkeypatch.setattr(provider := OpenAICompatibleProvider(
        "https://api.deepseek.com", "k", "m", 30
    ), "_post", lambda payload: {})
    with pytest.raises(RuntimeError):
        provider.generate("科技报国", "系统工程", [])


def test_ask_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """问答应返回模型文本。"""
    provider = _provider(monkeypatch, "这是回答内容")
    answer = provider.ask({"title": "案例A"}, "思政点是什么？")
    assert answer == "这是回答内容"
