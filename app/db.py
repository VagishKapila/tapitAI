from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    # Railway Postgres uses sslmode=require usually; SQLAlchemy handles if included.
    return create_engine(database_url, pool_pre_ping=True)
