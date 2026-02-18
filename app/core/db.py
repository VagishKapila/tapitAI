from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from loguru import logger

from app.core.config import DATABASE_URL

# --- Base (single source of truth) ---
Base = declarative_base()

# --- Engine ---
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

# --- Session factory ---
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

# --- SQL query logging ---
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    logger.debug(f"SQL: {statement} | params={parameters}")

# --- FastAPI dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()