from sqlalchemy import Column, String, Float, Boolean, DateTime, func
from app.db.base import Base

class Presence(Base):
    __tablename__ = "presence"

    user_id = Column(String, primary_key=True, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    venue_type = Column(String, nullable=True)
    is_stationary = Column(Boolean, default=True)
    discoverable = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
