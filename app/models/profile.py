from sqlalchemy import Column, String, Integer, Enum, DateTime, func, JSON
from app.core.db import Base
from app.schemas.enums import WingmanStyle, HeightPreference, IntentType


class Profile(Base):
    __tablename__ = "profile"

    user_id = Column(String, primary_key=True)

    height_inches = Column(Integer, nullable=True)

    # multi-select stored as JSON list: ["shorter", "same"]
    height_preferences = Column(JSON, nullable=True)

    wingman_style = Column(
        Enum(WingmanStyle, name="wingman_style_enum"),
        nullable=True
    )

    intent = Column(
        Enum(IntentType, name="intent_type_enum"),
        nullable=True
    )

    note_text = Column(String, nullable=True)

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

from sqlalchemy import JSON

# lifestyle tags like ["gym","travel","wine"]
Profile.lifestyle_tags = Column(JSON, nullable=True)

