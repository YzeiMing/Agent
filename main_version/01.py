import os
from typing import List

import chromadb

from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import pdfplumber

from langchain_community.embeddings import DashScopeEmbeddings

#加载.env中的环境变量
load_dotenv()
app = FastAPI(title='AI知识库问答系统')


#-------------大模型--------------ZFDG
llm = ChatOpenAI(
    model='deepseek-v4-pro',
    temperature=0.7,
    api_key=os.getenv('DEEPSEEK_API_KEY'),
    base_url=os.getenv('DEEPSEEK_BASE_URL'),
)


#-------------嵌入模型--------------
embeddings =DashScopeEmbeddings(
    model=os.getenv('EMBEDDING_MODEL_NAME',"text-embedding-v2"),
    dashscope_api_key=os.getenv('DASHSCOPE_API_KEY'),
)
# 1
#from sentence_transformers import SentenceTransformer
#embeddings = SentenceTransformer('BAAI/bge-small-zh-v1.5')
# 2
#from langchain_openai import OpenAIEmbeddings
# embeddings = OpenAIEmbeddings(
#     model=os.getenv('DEEPSEEK_EMBEDDING_MODEL'),
#     openai_api_key=os.getenv('DEEPSEEK_API_KEY'),
#     openai_api_base=os.getenv('DEEPSEEK_BASE_URL')
# )


#-------------Chromadb 客户端 + Collection--------------
chroma_client = chromadb.PersistentClient(path='./chroma_db')
collection = chroma_client.get_or_create_collection(name='docs_collection')


#-------------请求/响应模型--------------
class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str

class ChunkResponse(BaseModel):
    chunk_index: int
    text: str

class UploadResponse(BaseModel):
    filename:str
    total_chunks:int
    chunks:List[ChunkResponse]

#-------------工具函数-------------
async def chunk_text(text:str, chunk_size:int=500, overlap:int=50) -> List[str]:
    """
    将文本按固定字数切分成块，相邻之间有 overlap 重叠
    """
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        # 取当前块
        #text[start:end]:从字符串中截取一部分
        chunk = text[start:end]
        chunks.append(chunk)
        # 下一块的起始位置
        start = end - overlap
    return chunks

#-------------接口-------------
@app.get("/")
async def read_root():
    return {"message": "Hello RAG"}

@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    # 向量化问题
    question_emb = embeddings.embed_query(req.question)

    # 向量检索，取最相关的3个文本块
    results = collection.query(
        query_embeddings=question_emb,
        n_results=3
    )
    retrieved_chunks = results.get('documents', [[]])[0]

    # 拼接上下文
    if retrieved_chunks:
        context = "\n\n".join(retrieved_chunks)
        prompt = f"请根据以下参考资料回答用户的问题。 \n\n参考资料：\n{context}\n\n问题：{req.question}\n答案："
    else:
        prompt = req.question

    # 调用大模型
    response = llm.invoke(prompt)
    answer = response.content
    return AskResponse(answer=answer)

@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    # 检查文件类型
    # .endswith(''):判断字符串是否以特定内容结尾，返回True/False
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="目前只支持PDF文件")

    # 读取pdf内容并提取文本
    try:
        content = await file.read()
        # 通过BytesIO()创建临时文件，以便于用pdfplumber打开来操作PDF数据
        from io import BytesIO
        pdf_file = BytesIO(content)
        with pdfplumber.open(pdf_file) as pdf:
            full_text=''
            for page in pdf.pages:
                # page.extract_text():把PDF文件里的所有文字内容抽取出来，变成一个字符串
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + '\n'
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF解析失败：{str(e)}")

    # 删除full_text字符串两边的空白内容
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="PDF文件中未提取到任何文本")

    # 文本分块
    # 在同步函数中，直接调用了异步函数，却没有使用await导致变量实际上是一个”协程对象“而不是期望的”列表“ 如：不使用await得到的chunks
    chunks = await chunk_text(full_text, chunk_size=500, overlap=50)

    # 向量化并存入
    if chunks:
        # 生成向量
        chunk_embeddings = embeddings.embed_documents(chunks)
        # 给每个块一个唯一的ID(文件名+序号)
        ids = [f"{file.filename}_{i}" for i in range(len(chunk_embeddings))]
        # 存入集合
        collection.add(
            embeddings=chunk_embeddings,
            ids=ids,
            documents=chunks,
        )

    # 构造响应
    chunk_responses = [
        ChunkResponse(chunk_index=i, text=chunk)
        # enumerate(iterable, start=0):给可迭代对象添加索引，如[(0, chunk1),(1, chunk2)...]
        for i, chunk in enumerate(chunks)
    ]
    return UploadResponse(filename=file.filename,
                          total_chunks=len(chunks),
                          chunks=chunk_responses
    )



#uvicorn.run(app, host="0.0.0.0", port=8000)
#uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# 涉及到 FastAPI 的数据验证和文档生成机制。
# 1. 为什么是 question而不是 askrequest？
#
# 在你的代码中，AskRequest是一个 Pydantic 模型：
#
# FastAPI 文档中显示的请求体结构是由这个模型的字段定义决定的：
# 模型名 AskRequest是代码中的类名（在文档的 Schema 部分会显示）
# 但实际请求体的 JSON 结构是 { "question": "字符串" }，因为这是模型定义的字段
# 简单说：AskRequest是模型的“类型”，question是这个类型的“属性”。