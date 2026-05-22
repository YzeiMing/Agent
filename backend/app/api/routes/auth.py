from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_session
from backend.app.models.schemas import UserRegister, Token, UserOut
from backend.app.services.auth import create_user, get_user_by_email, verify_password, create_access_token

router = APIRouter()

@router.post("/register", response_model=UserOut)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_session)):
    # 检查邮箱是否存在
    existing = await get_user_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    user = await create_user(db, user_in.email, user_in.password, user_in.tenant_id)
    return user

@router.post("/token", response_model=Token)
async def login_for_access_token(
        # ???????? = Depends(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_session)
):
    user = await get_user_by_email(db, form_data.username) #username实际是email
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"}
        )
    access_token = create_access_token(data={"sub": user.email})
    return Token(access_token=access_token, token_type="bearer")