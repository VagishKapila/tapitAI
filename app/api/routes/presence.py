from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import math

from app.db.session import get_db
from app.core.auth import get_current_user_id
from app.core.match_config import (
    STATIONARY_THRESHOLD_SECONDS,
    PRESENCE_EXPIRY_MINUTES,
    AUTO_NUDGE_ENABLED,
)

router = APIRouter()


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class PresenceHeartbeatRequest(BaseModel):
    lat: float
    lng: float
    is_stationary: bool = True
    venue_type: str | None = None


class PresenceHeartbeatResponse(BaseModel):
    status: str
    last_seen_at: datetime


class NearbyRequest(BaseModel):
    lat: float
    lng: float
    radius_meters: int = 100


class NearbyUser(BaseModel):
    user_id: str
    lat: float
    lng: float
    distance_meters: float


class NearbyResponse(BaseModel):
    users: list[NearbyUser]
    conversation_id: str | None = None


# ------------------------------------------------------------------
# Utils
# ------------------------------------------------------------------

def haversine_m(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ------------------------------------------------------------------
# HEARTBEAT
# ------------------------------------------------------------------

@router.post("/heartbeat", response_model=PresenceHeartbeatResponse)
def presence_heartbeat(
    payload: PresenceHeartbeatRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    now = datetime.now()

    db.execute(
        text(
            """
            INSERT INTO presence (
                user_id,
                lat,
                lng,
                venue_type,
                is_stationary,
                discoverable,
                activated_at,
                last_seen_at
            )
            VALUES (
                :user_id,
                :lat,
                :lng,
                :venue_type,
                :is_stationary,
                TRUE,
                CASE WHEN :is_stationary THEN NOW() ELSE NULL END,
                NOW()
            )
            ON CONFLICT(user_id) DO UPDATE SET
                lat = excluded.lat,
                lng = excluded.lng,
                venue_type = excluded.venue_type,
                is_stationary = excluded.is_stationary,
                activated_at = CASE
                WHEN excluded.is_stationary = TRUE
                    AND presence.is_stationary = FALSE
                THEN NOW()
                WHEN excluded.is_stationary = FALSE
                THEN NULL
                ELSE presence.activated_at
            END,
                last_seen_at = NOW()
            """
        ),
        {
            "user_id": user_id,
            "lat": payload.lat,
            "lng": payload.lng,
            "venue_type": payload.venue_type,
            "is_stationary": payload.is_stationary,
        },
    )

    db.commit()

    return {"status": "ok", "last_seen_at": now}

# ------------------------------------------------------------------
# NEARBY + AUTO-NUDGE
# ------------------------------------------------------------------

@router.post("/nearby", response_model=NearbyResponse)
def presence_nearby(
    payload: NearbyRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    now = datetime.now()
    expiry_cutoff = now - timedelta(minutes=PRESENCE_EXPIRY_MINUTES)
    activation_cutoff = now - timedelta(seconds=STATIONARY_THRESHOLD_SECONDS)
    print("STATIONARY_THRESHOLD_SECONDS =", STATIONARY_THRESHOLD_SECONDS)

    # Debug current user
    me = db.execute(
        text("""
            SELECT activated_at, last_seen_at
            FROM presence
            WHERE user_id = :uid
        """),
        {"uid": user_id},
    ).fetchone()

    print("ME:", me)
    print("ACTIVATION_CUTOFF:", activation_cutoff)
    

    rows = db.execute(
        text(
            """
            SELECT user_id, lat, lng, activated_at, last_seen_at
            FROM presence
            WHERE
                discoverable = TRUE
                AND user_id != :user_id
                AND is_stationary = TRUE
                AND activated_at IS NOT NULL
                AND activated_at <= :activation_cutoff
                AND last_seen_at >= :expiry_cutoff
            """
        ),
        {
            "user_id": user_id,
            "activation_cutoff": activation_cutoff,
            "expiry_cutoff": expiry_cutoff,
        },
    ).fetchall()

    print("RAW ELIGIBLE ROWS:", rows)

    nearby_users = []

    for r in rows:
        distance = haversine_m(payload.lat, payload.lng, r.lat, r.lng)
        print("DISTANCE TO", r.user_id, "=", distance)

        if distance <= payload.radius_meters:
            nearby_users.append(
                NearbyUser(
                     user_id=str(r.user_id),
                    lat=r.lat,
                    lng=r.lng,
                    distance_meters=round(distance, 1),
                )
            )
    print("FINAL NEARBY USERS:", nearby_users)

    return {"users": nearby_users, "conversation_id": None}