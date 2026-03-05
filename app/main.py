from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger
from dotenv import load_dotenv

from app.core.logging import setup_logging
from app.core.init_db import init_db
from app.api.router import api_router
from app.modules.connections import router as connections_router
from app.modules.notifications.router import router as notifications_router
from app.api.push import router as push_router
from app.api.media import router as media_router
from app.modules.reveal_v2.router import router as reveal_v2_router
from app.modules.vault.router import router as vault_router
from app.api.routes import push_test
from app.modules.settings.router import router as settings_router
from app.modules.pulse.router import router as pulse_router
from app.modules.invitations.router import router as invitations_router
from app.modules.age_gate.router import router as age_router
from app.modules.safety_reports.router import router as safety_router
from app.modules.app_users.router import router as app_users_router
from app.modules.admin_dashboard.router import router as admin_router
from app.modules.frequent.router import router as frequent_router
from app.modules.frequent.scheduler import start_frequency_scheduler
start_frequency_scheduler()


from app.modules.frequent.router import router as frequent_router



load_dotenv()

setup_logging()
logger.info("Starting TapIn backend")

app = FastAPI(
    title="TapIn Backend",
    version="0.1.0",
)

# Routers
app.include_router(reveal_v2_router)
app.include_router(media_router)
app.include_router(push_test.router)
app.include_router(vault_router)
app.include_router(push_router)
app.include_router(api_router)  # includes presence routes etc
app.include_router(notifications_router)
app.include_router(connections_router)
app.include_router(settings_router)
app.include_router(pulse_router)
app.include_router(invitations_router)
app.include_router(age_router)
app.include_router(safety_router)
app.include_router(app_users_router)
app.include_router(admin_router)
app.include_router(frequent_router)
app.include_router(frequent_router)



# Static mounts
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="static/uploads"), name="uploads")

# Init DB after app is created
init_db()


@app.get("/health")
def health():
    logger.debug("Health check hit")
    return {"status": "ok"}

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}