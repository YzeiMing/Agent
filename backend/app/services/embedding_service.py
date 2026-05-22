from typing import List
from dashscope import TextEmbedding
from backend.app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#-------------嵌入模型--------------
def embed_texts(texts: List[str])->List[List[float]]:
    """
    使用同步接口，适合当前规模的文档处理
    """
    # TextEmbedding.call语法以及作用
    resp = TextEmbedding.call(
        model=settings.EMBEDDING_MODEL_NAME,
        api_key=settings.DASHSCOPE_API_KEY,
        input=texts
    )
    if resp.status_code != 200:
        logger.error(f"Embedding失败: {resp.status_code} - {resp.message}")
        # RuntimeError()
        raise RuntimeError(f"Embedding请求失败: {resp.message}")
    # 按顺序提取向量
    embeddings = [item["embedding"] for item in resp.output["embeddings"]]
    return embeddings

# 多条数据怎么写
def embed_query(text: str)->List[float]:
    """单条查询向量化"""
    return embed_texts([text])[0]