# ============================================================
# Qwen LLM 工厂（OpenAI 兼容接口）
# ============================================================
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache()
def get_llm() -> ChatOpenAI:
    """
    返回 Qwen 模型的 LangChain ChatOpenAI 实例。
    
    支持两种方式：
    1. 阿里云 DashScope（默认）：BASE_URL = https://dashscope.aliyuncs.com/compatible-mode/v1
    2. 本地部署（vLLM / Ollama 等）：修改 LLM_BASE_URL 即可
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=True,  # 启用流式输出
    )


def get_llm_model_name() -> str:
    return get_settings().LLM_MODEL
