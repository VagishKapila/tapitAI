from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from .engine import get_engine

# Create Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=get_engine(),
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
