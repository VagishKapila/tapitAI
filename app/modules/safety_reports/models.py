from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.db import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(String, nullable=False)
    reported_user_id = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String, default="open")
    created_at = Column(DateTime, server_default=func.now())
    reviewed_by = Column(String, nullable=True)
    action_taken = Column(Text, nullable=True)
