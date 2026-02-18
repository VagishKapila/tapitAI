from sqlalchemy import Column, String, Float, Boolean, DateTime, Index
from sqlalchemy.sql import func

from app.core.db import Base

class Presence(Base):
    __tablename__ = "presence"

    user_id = Column(String, primary_key=True, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    venue_type = Column(String, nullable=True)

    is_stationary = Column(Boolean, nullable=False, default=True)
    discoverable = Column(Boolean, nullable=False, default=True)

    last_seen_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_presence_location", "lat", "lng"),
        Index("idx_presence_last_seen", "last_seen_at"),
    )
