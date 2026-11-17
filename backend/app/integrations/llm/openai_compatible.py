"""OpenAI 兼容接口适配器，用于接入 DeepSeek 等模型服务。

遵循 OpenAI Chat Completions 协议：``POST {base_url}/chat/completions``。
生成阶段要求模型返回结构化 JSON，解析为多稿候选；问答阶段直接返回文本。
"""

import json
from typing import Any

import httpx

from app.core.timeutil import today_compact
from app.integrations.llm.base import Draft

_GENERATE_TEMPLATE = """你是课程思政案例库的案例编辑。请根据以下条件生成 3 个候选案例。

思政方向：{ideological}
专业知识点：{knowledge}
相关专业：{profession}

要求：
1. 每个案例的正文必须基于事实、表述严谨，不得编造具体数据或来源；
2. 思政元素从以下标签中选择：科技自立自强、自主创新、科技报国、攻坚克难、团结协作、严谨求实、工匠精神、家国情怀、责任担当、国际合作、人民至上、创新驱动发展、文化自信、诚实守信、法治精神、生态文明、艰苦奋斗、开拓进取；
3. 只返回 JSON，不要输出任何解释或 Markdown。

返回格式：
{{"drafts": [
  {{
    "case": {{
      "title": "案例标题",
      "category": "人物案例/政策文件/行业案例/新闻资讯/专业资料/项目资料",
      "source": "来源单位",
      "source_url": "",
      "publish_date": "YYYYMMDD",
      "background": "背景摘要",
      "process": "实施过程",
      "result": "成果成效",
      "profession": ["专业名称"],
      "keywords": ["关键词"],
      "professional_knowledge": ["专业知识点"],
      "ideological_elements": ["思政标签"],
      "teaching_value": "教学价值"
    }},
    "evaluation": {{
      "totalScore": 88,
      "dimensions": [{{"name": "思政相关性", "score": 90, "comment": "评价"}}],
      "suggestions": ["修改建议"]
    }}
  }}
]}}
"""

_ASK_TEMPLATE = """你是课程思政案例助手。请基于下面这个案例回答用户问题，回答要引用案例内容，不要编造案例之外的事实。

案例信息：
{case}

用户问题：{question}
"""


def _strip_markdown_fence(text: str) -> str:
    """去掉模型偶尔包裹的 ```json 代码块。"""
    content = text.strip()
    if content.startswith("```"):
        content = content[3:]
        if content.lower().startswith("json"):
            content = content[4:]
        if content.endswith("```"):
            content = content[:-3]
    return content.strip()


class OpenAICompatibleProvider:
    """OpenAI 兼容协议的模型提供方。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """发送请求；独立成方法便于测试替换。"""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    def _chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.7,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        data = self._post(payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("模型响应格式异常") from exc

    def generate(
        self,
        ideological: str,
        knowledge: str,
        profession: list[str],
    ) -> list[Draft]:
        """生成三稿候选；模型返回异常时抛 RuntimeError 交由上层处理。"""
        profession_text = "、".join(profession) if profession else "相关专业"
        prompt = _GENERATE_TEMPLATE.format(
            ideological=ideological,
            knowledge=knowledge,
            profession=profession_text,
        )
        content = self._chat(
            [
                {"role": "system", "content": "你是课程思政案例编辑，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            json_mode=True,
        )

        try:
            data = json.loads(_strip_markdown_fence(content))
        except json.JSONDecodeError as exc:
            raise RuntimeError("模型返回的 JSON 无法解析") from exc

        drafts: list[Draft] = []
        for item in data.get("drafts", []):
            case = dict(item.get("case") or {})
            evaluation = dict(item.get("evaluation") or {})
            case.setdefault("category", "行业案例")
            case.setdefault("source", "AI生成")
            case.setdefault("sourceType", "AI生成")
            case.setdefault("review_status", "草稿")
            case.setdefault("publish_date", today_compact())
            case.setdefault("collect_date", today_compact())
            case.setdefault("version", "V1.0")
            case.setdefault("content", "")
            drafts.append(Draft(case=case, evaluation=evaluation))
        return drafts

    def ask(self, case_context: dict[str, Any], question: str) -> str:
        """基于案例上下文生成回答。"""
        prompt = _ASK_TEMPLATE.format(
            case=json.dumps(case_context, ensure_ascii=False),
            question=question,
        )
        return self._chat(
            [
                {"role": "system", "content": "你是课程思政案例助手。"},
                {"role": "user", "content": prompt},
            ]
        )
