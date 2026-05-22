from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from backend.app.core.database import Base

#??????
class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    tenant_id = Column(String, index=True, nullable=False)
    plan = Column(String, default="free") # 订阅
    is_active = Column(Boolean, default=True) # ?
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # ?

