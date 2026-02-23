from sqlalchemy import Column, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.db import Base


class PushToken(Base):
    __tablename__ = "push_token"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    expo_push_token = Column(Text, nullable=False)

    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
