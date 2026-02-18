from loguru import logger
from app.core.db import engine, Base

# Import all models so SQLAlchemy registers them
from app.models.profile import Profile
from app.models.onboarding import OnboardingState
from app.models.media import MediaItem
from app.models.presence import Presence

# 🔹 NEW: import connections models
from app.modules.connections.models import Connection, Conversation, Message

def init_db():
    logger.info("Creating database tables")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")