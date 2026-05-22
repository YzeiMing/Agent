import uuid
import logging
from fastapi import File, UploadFile, HTTPException, BackgroundTasks, APIRouter, Depends
from backend.app.models.schemas import UploadResponse
from backend.app.utils.text_utils import chunk_text
from backend.app.services.vector_store import add_documents
from backend.app.services.embedding_service import embed_texts
import pdfplumber
from io import BytesIO
from backend.app.api.dependencies import get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def process_pdf_and_store(file_content:bytes, filename:str):
    """
    后台任务：解析PDF - 分块 - 向量化 - 存入Chroma
    """
    try:
        # 提取文本
        pdf_file = BytesIO(file_content)
        with pdfplumber.open(pdf_file) as f:
            full_text=""
            for page in f.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
        if not full_text.strip():
            logger.warning(f"文件{filename}未提取到文本")
            return

        # 分块
        chunks = chunk_text(full_text)
        logger.info(f"文件{filename}分为{len(chunks)}块，开始向量化")

        # 向量化 就是如果一个def函数加了async，那怎么才算协程对象？
        embeddings = embed_texts(chunks)

        # 存入Chroma
        ids = [f"{filename}_{uuid.uuid4().hex[:8]}" for _ in chunks]
        add_documents(embeddings, chunks, ids)
        logger.info(f"文件{filename}处理完成，已存入{len(chunks)}条记录")

    except Exception as e:
        logger.error(f"处理文件{filename} 失败{str(e)}")

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None
):
    # 检查文件类型
    # .endswith(''):判断字符串是否以特定内容结尾，返回True/False
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持PDF文件")

    # 读取pdf内容并提取文本
    try:
        content = await file.read()
        # 立即返回，实际处理在后台执行
        background_tasks.add_task(process_pdf_and_store, content, file.filename)
        logger.info(f"收到文件{file.filename}，已加入后台处理队列")
        return UploadResponse(
            filename=file.filename,
            # 那这里的total_chunks:Optional[int]=None呢
            message="文件已接收，正在后台处理中",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败：{str(e)}")


@router.get("/test-protected")
async def test_protected(current_user = Depends(get_current_user)):
    return {"message": f"你好{current_user.email}，你已通过验证", "tenant_id": current_user.tenant_id}