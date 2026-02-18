from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    Enum,
    func
)
from app.core.db import Base
from app.schemas.enums import OnboardingStep


class OnboardingState(Base):
    __tablename__ = "onboarding_state"

    user_id = Column(String, primary_key=True)
    version = Column(Integer, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)

    current_step = Column(
        Enum(OnboardingStep, name="onboarding_step_enum"),
        nullable=False
    )

    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
