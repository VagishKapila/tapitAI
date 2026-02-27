from fastapi import FastAPI
from loguru import logger

from app.core.logging import setup_logging
from app.core.init_db import init_db
from app.api.router import api_router
from app.modules.connections import router as connections_router
from app.modules.notifications.router import router as notifications_router
from app.api.push import router as push_router
from fastapi.staticfiles import StaticFiles
from fastapi.staticfiles import StaticFiles
from app.api.media import router as media_router
from app.modules.reveal_v2.router import router as reveal_v2_router
from app.modules.vault.router import router as vault_router

from app.api.routes import push_test
from dotenv import load_dotenv
load_dotenv()

setup_logging()
logger.info("Starting TapIn backend")



app = FastAPI(
    title="TapIn Backend",
    version="0.1.0"
)

app.include_router(reveal_v2_router)
app.include_router(media_router)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(push_test.router)
app.mount("/uploads", StaticFiles(directory="static/uploads"), name="uploads")
app.include_router(vault_router)

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