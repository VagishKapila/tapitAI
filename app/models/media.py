from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.db import Base

class MediaItem(Base):
    __tablename__ = "media_item"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    media_type = Column(String, nullable=False)  # image | video
    order_index = Column(Integer, nullable=False)
    is_primary = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
