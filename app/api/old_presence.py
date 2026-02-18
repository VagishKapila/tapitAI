from fastapi import APIRouter, Header
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/v1/presence", tags=["presence"])

ACTIVE_USERS = {}

class HeartbeatPayload(BaseModel):
    lat: float
    lng: float

@router.post("/heartbeat")
def heartbeat(
    payload: HeartbeatPayload,
    x_user_id: str = Header(...),
):
    ACTIVE_USERS[x_user_id] = {
        "lat": payload.lat,
        "lng": payload.lng,
        "last_seen": datetime.utcnow()
    }
    return {"status": "ok"}

@router.post("/nearby")
def nearby(x_user_id: str = Header(...)):
    now = datetime.utcnow()
    results = []

    me = ACTIVE_USERS.get(x_user_id)
    if not me:
        return []

    for user_id, data in ACTIVE_USERS.items():
        if user_id == x_user_id:
            continue

        if now - data["last_seen"] < timedelta(seconds=60):
            results.append({
                "user_id": user_id,
                "lat": data["lat"],
                "lng": data["lng"],
                "distance_meters": 5
            })

    return results