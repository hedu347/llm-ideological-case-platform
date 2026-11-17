"""按配置选择 AI 提供方。"""

from app.core.config import Settings
from app.integrations.llm import builtin
from app.integrations.llm.base import LLMProvider


def get_provider(settings: Settings) -> LLMProvider:
    """返回当前可用的生成器。

    演示阶段只启用内置生成器；``openai`` / ``maxkb`` 分支在真实模型
    接入后补充，在此之前统一回退到内置生成器，避免演示中断。
    """
    return builtin
