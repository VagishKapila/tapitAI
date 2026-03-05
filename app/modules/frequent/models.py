from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.db.base import Base


class UserLocationSession(Base):
    __tablename__ = "user_location_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)

    lat = Column(Float)
    lng = Column(Float)

    geohash = Column(String, index=True)

    start_ts = Column(DateTime)
    end_ts = Column(DateTime)

    duration_sec = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())


class UserFrequent(Base):
    __tablename__ = "user_frequents"

    id = Column(String, primary_key=True)

    user_id = Column(String, index=True)
    candidate_user_id = Column(String, index=True)

    encounter_count = Column(Integer, default=0)

    first_seen_at = Column(DateTime)
    last_seen_at = Column(DateTime)

    dismissed = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
