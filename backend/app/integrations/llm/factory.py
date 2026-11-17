"""按配置选择 AI 提供方。"""

from app.core.config import Settings
from app.integrations.llm import builtin
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.openai_compatible import OpenAICompatibleProvider


def get_provider(settings: Settings) -> LLMProvider:
    """返回当前配置可用的生成器。

    ``openai`` 需要同时提供 base_url、api_key 与 model；任一项缺失或请求
    失败时，调用方会捕获异常并回退到内置生成器，保证演示不中断。
    """
    if (
        settings.llm_provider == "openai"
        and settings.llm_base_url is not None
        and settings.llm_api_key is not None
        and settings.llm_api_key.get_secret_value()
    ):
        return OpenAICompatibleProvider(
            base_url=str(settings.llm_base_url),
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model or "deepseek-chat",
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return builtin
