import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # DeepSeek
    LLM_MODEL_NAME: str  = os.getenv("LLM_MODEL_NAME")
    DEEPSEEK_API_KEY: str = os.getenv('DEEPSEEK_API_KEY', "")
    DEEPSEEK_BASE_URL: str  = os.getenv('DEEPSEEK_BASE_URL', "https://api.deepseek.com")

    # 嵌入模型
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME")
    DASHSCOPE_API_KEY: str = os.getenv('DASHSCOPE_API_KEY', "")

    # 向量库
    CHROMA_PERSIST_PATH: str = os.getenv("CHROMA_PERSIST_PATH")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME")

    # 数据库
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

settings = Settings()


