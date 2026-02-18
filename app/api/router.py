from fastapi import APIRouter

from app.api.routes import onboarding
from app.api.routes import presence

api_router = APIRouter(prefix="/v1")

api_router.include_router(onboarding.router, tags=["onboarding"])
api_router.include_router(presence.router, prefix="/presence", tags=["presence"])