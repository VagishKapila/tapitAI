from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from app.db.session import Base

class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    expo_push_token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
