import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

def _get_env(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if val is None:
        raise RuntimeError(f"Missing required env var: {key}")
    return val

APP_ENV = _get_env("APP_ENV", "local")
DATABASE_URL = _get_env("DATABASE_URL", "postgresql+psycopg2://vagkapi:password@localhost:5432/tapitai")
LOG_LEVEL = _get_env("LOG_LEVEL", "DEBUG")

logger.debug(f"Config loaded: APP_ENV={APP_ENV}, DATABASE_URL={DATABASE_URL}, LOG_LEVEL={LOG_LEVEL}")
