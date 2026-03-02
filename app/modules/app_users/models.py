from sqlalchemy import Column, String, Boolean, Integer, TIMESTAMP, text
from app.db.base_class import Base

class AppUser(Base):
    __tablename__ = "app_users"

    user_id = Column(String, primary_key=True, index=True)
    phone = Column(String, nullable=True)

    created_at = Column(
        TIMESTAMP,
        server_default=text("now()"),
        nullable=False
    )

    invite_verified = Column(Boolean, default=False)
    invite_verified_at = Column(TIMESTAMP, nullable=True)
    invite_code_used = Column(String, nullable=True)

    age_int = Column(Integer, nullable=True)
    age_set_at = Column(TIMESTAMP, nullable=True)
