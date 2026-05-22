from langchain_openai import ChatOpenAI

# 将backend目录标记为源代码根目录
from backend.app.core.config import settings

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        temperature=0.7,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL
    )