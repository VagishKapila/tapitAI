from sqlalchemy import Column, String, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from app.db import Base


class MediaItem(Base):
    __tablename__ = "media_item"

    id = Column(UUID(as_uuid=False), primary_key=True)
    user_id = Column(UUID(as_uuid=False), nullable=False)
    media_type = Column(String, nullable=False)
    order_index = Column(Integer, nullable=False)
    is_primary = Column(Boolean, default=False)
    file_path = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)