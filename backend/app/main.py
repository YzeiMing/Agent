import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from backend.app.api.routes import ask, upload, auth
from backend.app.core.database import async_engine, Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建所有表（生产环境应使用Alembic迁移）
async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# 定义 lifespan 上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑
    print("启动应用程序...")
    async def startup():
        await create_tables()
    await startup()
    # yield 之后是运行期
    yield
    # 关闭逻辑
    print("关闭应用程序...")
    await async_engine.dispose()

app = FastAPI(title='AI知识库问答系统',lifespan=lifespan)

# 注册路由
app.include_router(auth.router) # 注册、登录
app.include_router(upload.router)
app.include_router(ask.router)

@app.get("/")
def root():
    return {"message": "Hello World"}

#uvicorn.run(app, host="0.0.0.0", port=8000)
#python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
