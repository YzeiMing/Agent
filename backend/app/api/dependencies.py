from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.database import get_session
from backend.app.services.auth import get_user_by_email

oauth2_schema = HTTPBearer()

#当你点击 Authorize 并输入 Token 后，Swagger UI 会：
#1、保存 Token 在浏览器的 LocalStorage 里
#2、自动注入 Header 到每一个请求中
async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(oauth2_schema),  # 改这里
        db: AsyncSession = Depends(get_session)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user




# from fastapi import Depends, FastAPI, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from jose import jwt, JWTError
# from sqlalchemy.ext.asyncio import AsyncSession
# from backend.app.core.config import settings
# from backend.app.core.database import get_session
# from backend.app.services.auth import get_user_by_email
#
# # ?????
# oauth2_schema = OAuth2PasswordBearer(tokenUrl="/token")
#
# async def get_current_user(
#         token: str = Depends(oauth2_schema),
#         db: AsyncSession = Depends(get_session)
# ):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="无法验证凭据",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
#         email: str = payload.get("sub")
#         if email is None:
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception
#
#     user = await get_user_by_email(db, email=email)
#     if user is None:
#         raise credentials_exception
#     return user



