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


def _pair_low_high(a, b) -> tuple[str, str]:
    a_str = str(a)
    b_str = str(b)
    return (a_str, b_str) if a_str < b_str else (b_str, a_str)


def _is_blocked_pair(db: Session, me, other) -> bool:
    low, high = _pair_low_high(me, other)

    row = db.execute(
        text(
            """
            select 1
            from public.reveal_blocklist_v2
            where user_low = :low and user_high = :high
            """
        ),
        {"low": low, "high": high},
    ).mappings().first()

    return row is not None


def _today_cycle_targets(db: Session, viewer_id: str, day_key) -> list[str]:
    rows = db.execute(
        text(
            """
            select target_id
            from public.reveal_daily_cycle_v2
            where viewer_id = :viewer_id and day_key = :day_key
            order by slot asc
            """
        ),
        {"viewer_id": viewer_id, "day_key": day_key},
    ).mappings().all()

    return [str(r["target_id"]) for r in rows if r.get("target_id")]

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
# NEARBY + 3-CYCLE V2 FILTER
# ------------------------------------------------------------------

@router.post("/nearby", response_model=NearbyResponse)
def presence_nearby(
    payload: NearbyRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    now = datetime.now()
    day_key = now.date()

    expiry_cutoff = now - timedelta(minutes=PRESENCE_EXPIRY_MINUTES)
    activation_cutoff = now - timedelta(seconds=STATIONARY_THRESHOLD_SECONDS)

    # Get today's cycle targets first (these are the ONLY 3 we ever show today)
    todays_targets = _today_cycle_targets(db, user_id, day_key)
    todays_set = set(todays_targets)

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

    # distance filter first
    in_radius: list[tuple[str, float, float, float]] = []
    for r in rows:
        distance = haversine_m(payload.lat, payload.lng, r.lat, r.lng)
        if distance <= payload.radius_meters:
            in_radius.append((str(r.user_id), float(r.lat), float(r.lng), float(distance)))

    # If we already have 3 today, ONLY return those 3 (if still around)
    if len(todays_targets) >= 3:
        out: list[NearbyUser] = []
        for uid, lat, lng, dist in in_radius:
            if uid in todays_set:
                out.append(
                    NearbyUser(user_id=uid, lat=lat, lng=lng, distance_meters=round(dist, 1))
                )
        # preserve the cycle ordering (slot order)
        out.sort(key=lambda u: todays_targets.index(u.user_id) if u.user_id in todays_set else 999)
        return {"users": out, "conversation_id": None}

    # Otherwise: show today's existing first, then fill remaining slots with new users,
    # excluding blocklisted pairs (prior passes/meets), but allowing today's already-picked users.
    already_out: list[NearbyUser] = []
    fresh_candidates: list[NearbyUser] = []

    for uid, lat, lng, dist in in_radius:
        if uid in todays_set:
            already_out.append(
                NearbyUser(user_id=uid, lat=lat, lng=lng, distance_meters=round(dist, 1))
            )
            continue

        # exclude prior passes/meets forever
        if _is_blocked_pair(db, user_id, uid):
            continue

        fresh_candidates.append(
            NearbyUser(user_id=uid, lat=lat, lng=lng, distance_meters=round(dist, 1))
        )

    already_out.sort(key=lambda u: todays_targets.index(u.user_id) if u.user_id in todays_set else 999)

    # fill up to 3 total
    remaining = 3 - len(already_out)
    if remaining < 0:
        remaining = 0

    # stable + simple fill order: nearest first
    fresh_candidates.sort(key=lambda u: u.distance_meters)

    combined = already_out + fresh_candidates[:remaining]
    return {"users": combined, "conversation_id": None}