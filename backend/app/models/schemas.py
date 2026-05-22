from pydantic import BaseModel
from typing import Optional, List

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str

class UploadResponse(BaseModel):
    filename: str
    message: str
    total_chunks: Optional[int] = None

#-----认证-----
class UserRegister(BaseModel):
    email: str
    password: str
    tenant_id: str # ??

# ??????
class Token(BaseModel):
    access_token: str
    token_type: str

class UserOut(BaseModel):
    id: int
    email: str
    tenant_id: str
    plan: str
    
