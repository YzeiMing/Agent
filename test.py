import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagModel
load_dotenv()

#os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'


emb = FlagModel('BAAI/bge-small-zh-v1.5',
                query_instruction_for_retrieval='',
                use_fp16=True)

# 测试单个查询
vec = emb.embed_query("测试文本")
print(f"向量维度: {len(vec)}")
print("Embedding 调用成功！")