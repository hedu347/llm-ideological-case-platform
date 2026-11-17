"""AI 适配层抽象类型。"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Draft:
    """一个候选案例及其辅助评价。"""

    case: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    """生成与问答的最小接口。"""

    def generate(
        self,
        ideological: str,
        knowledge: str,
        profession: list[str],
    ) -> list[Draft]:
        """按生成条件产出多稿候选。"""
        ...

    def ask(self, case_context: dict[str, Any], question: str) -> str:
        """基于单个案例上下文回答问题。"""
        ...
