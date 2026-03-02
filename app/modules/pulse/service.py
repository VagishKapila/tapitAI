from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text


WAVE_SECONDS = 600  # 10 minutes
NEARBY_RADIUS_METERS = 500  # real-life default (tune later)
PRESENCE_FRESH_SECONDS = 20 * 60  # must be "recently seen"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    # Same math style as your presence route (kept here to avoid importing it)
    import math

    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _get_viewer_presence(db: Session, viewer_id: str) -> Optional[Tuple[float, float]]:
    row = db.execute(
        text("""
            select lat, lng
            from public.presence
            where user_id = :uid
            limit 1
        """),
        {"uid": viewer_id},
    ).mappings().first()

    if not row:
        return None

    try:
        return float(row["lat"]), float(row["lng"])
    except Exception:
        return None


def _get_nearby_user_ids(db: Session, viewer_id: str, center_lat: float, center_lng: float) -> List[str]:
    # Pull candidates from presence table, then filter by haversine in python.
    # This avoids PostGIS assumptions and stays compatible with your current setup.
    cutoff = _utcnow() - timedelta(seconds=PRESENCE_FRESH_SECONDS)

    rows = db.execute(
        text("""
            select user_id, lat, lng, last_seen_at
            from public.presence
            where user_id != :viewer_id
              and last_seen_at is not null
              and last_seen_at >= :cutoff
        """),
        {"viewer_id": viewer_id, "cutoff": cutoff},
    ).mappings().all()

    nearby: List[Tuple[str, float]] = []
    for r in rows:
        try:
            uid = str(r["user_id"])
            lat = float(r["lat"])
            lng = float(r["lng"])
        except Exception:
            continue

        dist = _haversine_m(center_lat, center_lng, lat, lng)
        if dist <= NEARBY_RADIUS_METERS:
            nearby.append((uid, dist))

    # closer first
    nearby.sort(key=lambda x: x[1])
    return [uid for uid, _dist in nearby]


def _close_expired_waves(db: Session) -> None:
    now = _utcnow()
    db.execute(
        text("""
            update public.pulse_wave
            set status = 'closed'
            where status = 'active'
              and ends_at <= :now
        """),
        {"now": now},
    )
    db.commit()


def _get_active_wave(db: Session) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text("""
            select *
            from public.pulse_wave
            where status = 'active'
            order by started_at desc
            limit 1
        """)
    ).mappings().first()
    return dict(row) if row else None


def _create_wave(db: Session) -> Dict[str, Any]:
    now = _utcnow()
    ends_at = now + timedelta(seconds=WAVE_SECONDS)

    row = db.execute(
        text("""
            insert into public.pulse_wave (started_at, ends_at, status)
            values (:started_at, :ends_at, 'active')
            returning id, started_at, ends_at, status, created_at
        """),
        {"started_at": now, "ends_at": ends_at},
    ).mappings().first()

    db.commit()
    return dict(row)


def _ensure_wave(db: Session) -> Dict[str, Any]:
    _close_expired_waves(db)
    wave = _get_active_wave(db)
    if wave:
        return wave
    return _create_wave(db)


def _get_wave_entry_user_id(db: Session, wave_id: str) -> Optional[str]:
    row = db.execute(
        text("""
            select user_id
            from public.pulse_entry
            where wave_id = :wave_id
            limit 1
        """),
        {"wave_id": wave_id},
    ).mappings().first()
    return str(row["user_id"]) if row and row.get("user_id") else None


def _set_wave_entry(db: Session, wave_id: str, user_id: str) -> None:
    # ensure 1 entry per wave
    db.execute(
        text("""
            insert into public.pulse_entry (wave_id, user_id)
            values (:wave_id, :user_id)
            on conflict do nothing
        """),
        {"wave_id": wave_id, "user_id": user_id},
    )
    db.commit()


def _pick_spotlight_user_id(db: Session, viewer_id: str) -> Optional[str]:
    """
    Always return someone if database has any users.
    """

    # 1. Any presence user
    row = db.execute(
        text("""
            select user_id
            from public.presence
            where user_id != :viewer_id
            order by last_seen_at desc nulls last
            limit 1
        """),
        {"viewer_id": viewer_id},
    ).mappings().first()

    if row:
        return str(row["user_id"])

    # 2. Any user with media
    row = db.execute(
        text("""
            select user_id
            from public.media_item
            where user_id != :viewer_id
            limit 1
        """),
        {"viewer_id": viewer_id},
    ).mappings().first()

    if row:
        return str(row["user_id"])

    # 3. ANY profile user
    row = db.execute(
        text("""
            select id
            from public.profiles
            where id != :viewer_id
            limit 1
        """),
        {"viewer_id": viewer_id},
    ).mappings().first()

    if row:
        return str(row["id"])

    # 4. Absolute fallback — even if only one user exists
    row = db.execute(
        text("""
            select id
            from public.profiles
            limit 1
        """)
    ).mappings().first()

    if row:
        return str(row["id"])

    return None


def _get_user_edge_and_badges(db: Session, user_id: str) -> Tuple[str, List[str]]:
    # Your DB has BOTH:
    # - public.profiles (id, gender, interested_in, etc.)
    # - public.profile  (user_id, intent, lifestyle_tags, note_text, wingman_style, height_inches, etc.)
    # We use public.profile for edge/badges because it's onboarding-specific.

    row = db.execute(
        text("""
            select intent, note_text, lifestyle_tags
            from public.profile
            where user_id = :uid
            limit 1
        """),
        {"uid": user_id},
    ).mappings().first()

    edge = ""
    badges: List[str] = []

    if row:
        note_text = row.get("note_text") or ""
        intent = row.get("intent") or ""
        lifestyle_tags = row.get("lifestyle_tags") or []

        edge = str(note_text).strip()
        if intent:
            badges.append(str(intent).strip().capitalize())

        # lifestyle_tags is stored as JSON array in your row (based on your select output)
        if isinstance(lifestyle_tags, list):
            for t in lifestyle_tags:
                if t:
                    badges.append(str(t).strip().capitalize())

    if not edge:
        edge = "Tap to view more."

    # De-dupe while preserving order
    seen = set()
    uniq: List[str] = []
    for b in badges:
        key = b.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(b)
    return edge, uniq


def _infer_media_type(file_path: str) -> str:
    p = (file_path or "").lower()
    if p.endswith(".mp4") or p.endswith(".mov") or p.endswith(".m4v"):
        return "video"
    return "image"


def _get_user_media(db: Session, user_id: str) -> List[Dict[str, str]]:
    rows = db.execute(
        text("""
            select id, file_path
            from public.media_item
            where user_id = :uid
            order by created_at asc nulls last
        """),
        {"uid": user_id},
    ).mappings().all()

    media: List[Dict[str, str]] = []
    for r in rows:
        fp = r.get("file_path")
        if not fp:
            continue
        media.append({"type": _infer_media_type(str(fp)), "file_path": str(fp)})
    return media


def _count_votes(db: Session, wave_id: str, target_user_id: Optional[str]) -> int:
    if not target_user_id:
        return 0
    row = db.execute(
        text("""
            select count(*) as c
            from public.pulse_vote
            where wave_id = :wave_id
              and target_user_id = :tid
        """),
        {"wave_id": wave_id, "tid": target_user_id},
    ).mappings().first()
    return int(row["c"]) if row and row.get("c") is not None else 0


def _viewer_count_estimate(db: Session, viewer_id: str) -> int:
    # Lightweight estimate for UI (not a promise).
    # Count "nearby presences" including viewer, fresh in last N minutes, in radius.
    presence = _get_viewer_presence(db, viewer_id)
    if not presence:
        return 0

    center_lat, center_lng = presence
    cutoff = _utcnow() - timedelta(seconds=PRESENCE_FRESH_SECONDS)

    rows = db.execute(
        text("""
            select user_id, lat, lng
            from public.presence
            where last_seen_at is not null
              and last_seen_at >= :cutoff
        """),
        {"cutoff": cutoff},
    ).mappings().all()

    count = 0
    for r in rows:
        try:
            lat = float(r["lat"])
            lng = float(r["lng"])
        except Exception:
            continue
        dist = _haversine_m(center_lat, center_lng, lat, lng)
        if dist <= NEARBY_RADIUS_METERS:
            count += 1
    return count


def get_current_pulse(db: Session, viewer_id: str) -> Dict[str, Any]:
    wave = _ensure_wave(db)
    wave_id = str(wave["id"])
    ends_at = wave["ends_at"]

    spotlight_user_id = _get_wave_entry_user_id(db, wave_id)

    # If wave has no entry, pick one using real-life proximity
    if not spotlight_user_id:
        picked = _pick_spotlight_user_id(db, viewer_id)
        if picked:
            _set_wave_entry(db, wave_id, picked)
            spotlight_user_id = picked

    viewer_est = _viewer_count_estimate(db, viewer_id)
    vote_count = _count_votes(db, wave_id, spotlight_user_id)

    if not spotlight_user_id:
        return {
            "wave_id": wave_id,
            "ends_at": ends_at.isoformat(),
            "viewer_count_estimate": viewer_est,
            "vote_count": vote_count,
            "user": None,
        }

    edge, badges = _get_user_edge_and_badges(db, spotlight_user_id)
    media = _get_user_media(db, spotlight_user_id)

    return {
        "wave_id": wave_id,
        "ends_at": ends_at.isoformat(),
        "viewer_count_estimate": viewer_est,
        "vote_count": vote_count,
        "user": {
            "user_id": spotlight_user_id,
            "edge": edge,
            "badges": badges,
            "media": media,
        },
    }


def cast_vote(db: Session, voter_id: str, wave_id: str, target_user_id: str) -> None:
    # Prevent self vote
    if str(voter_id) == str(target_user_id):
        raise ValueError("Cannot vote for yourself")

    # Must be active wave
    wave = db.execute(
        text("""
            select id
            from public.pulse_wave
            where id = :wid and status = 'active'
            limit 1
        """),
        {"wid": wave_id},
    ).mappings().first()
    if not wave:
        raise ValueError("Wave is not active")

    # Insert vote (unique index prevents duplicates)
    db.execute(
        text("""
            insert into public.pulse_vote (wave_id, voter_id, target_user_id)
            values (:wave_id, :voter_id, :target_user_id)
            on conflict do nothing
        """),
        {"wave_id": wave_id, "voter_id": voter_id, "target_user_id": target_user_id},
    )
    db.commit()
