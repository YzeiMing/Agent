from fastapi import APIRouter
from backend.app.models.schemas import AskRequest, AskResponse
from backend.app.services.llm_service import get_llm
from backend.app.services.vector_store import query_documents
from backend.app.services.embedding_service import embed_query

router = APIRouter()

@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    # 检索
    question = embed_query(req.question)
    retrieved_chunks = query_documents(question)

    # 构建提示词
    if retrieved_chunks:
        context = "\n\n".join(retrieved_chunks)
        prompt = f"请根据以下参考资料回答用户的问题。 \n\n参考资料：\n{context}\n\n问题：{req.question}\n答案："
    else:
         prompt = req.question

    # 调用大模型
    llm = get_llm()
    response = llm.invoke(prompt)
    answer = response.content
    return AskResponse(answer=answer)
