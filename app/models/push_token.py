from sqlalchemy import Column, String, DateTime, func
from app.models.base import Base

class PushToken(Base):
    __tablename__ = "push_tokens"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    expo_token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
