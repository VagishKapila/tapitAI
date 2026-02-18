from fastapi import APIRouter
from loguru import logger

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])

@router.get("/sandbox-test")
def sandbox_test():
    logger.info("Notifications sandbox route hit")
    return {"notifications": "sandbox ok"}
