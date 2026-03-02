from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.db import Base


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, nullable=False)
    max_uses = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class InviteUsage(Base):
    __tablename__ = "invite_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invite_code_id = Column(UUID(as_uuid=True), ForeignKey("invite_codes.id"))
    user_id = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    used_at = Column(DateTime, server_default=func.now())


class WaitlistRequest(Base):
    __tablename__ = "waitlist_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String, nullable=False)
    name = Column(String, nullable=True)
    requested_at = Column(DateTime, server_default=func.now())
