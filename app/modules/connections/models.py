from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from app.core.db import Base


class Connection(Base):
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=False, index=True)
    status = Column(
        String,
        CheckConstraint(
            "status IN ('pending','accepted','rejected','expired')",
            name="connections_status_check",
        ),
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_a = Column(String, nullable=False, index=True)
    user_b = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(String, nullable=False)
    body = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
