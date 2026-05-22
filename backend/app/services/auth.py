from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.core.config import settings
from backend.app.models.db_models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    print("🔑 RAW PASSWORD:", repr(password))
    print("📏 BYTE LENGTH:", len(password.encode("utf-8")))
    print("PASSWORD:", repr(password))
    print("BYTE LEN:", len(password.encode("utf-8")))
    return pwd_context.hash(password)

def verify_password(plain_password: str, hased_password: str) -> bool:
    return pwd_context.verify(plain_password, hased_password)

def create_access_token(data:dict, expire_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expire_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KET, algorithm=settings.ALGORITHM)

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

# 在路由层面用schema来验证客户端的数据，再去调用函数传入相关参数
async def create_user(db: AsyncSession, email: str, password: str, tenant_id: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        tenant_id=tenant_id
    )
    # .add()??
    db.add(user)
    await db.commit()
    # ??????
    await db.refresh(user)
    return user