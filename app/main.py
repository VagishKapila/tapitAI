from fastapi import FastAPI
from loguru import logger

from app.core.logging import setup_logging
from app.core.init_db import init_db
from app.api.router import api_router
from app.modules.connections import router as connections_router
from app.modules.notifications.router import router as notifications_router
from app.api.push import router as push_router

from app.api.routes import push_test

setup_logging()
logger.info("Starting TapIn backend")



app = FastAPI(
    title="TapIn Backend",
    version="0.1.0"
)


app.include_router(push_test.router)

app.include_router(push_router)
# All API routes (includes presence via router.py)
app.include_router(api_router)

app.include_router(notifications_router)
# Connections module
app.include_router(connections_router)

# Init DB after app is created
init_db()

@app.get("/health")
def health():
    logger.debug("Health check hit")
    return {"status": "ok"}