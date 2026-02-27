from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.core.auth import get_current_user_id

router = APIRouter(prefix="/v2/reveal", tags=["reveal_v2"])

Decision = Literal["meet", "pass"]


# -----------------------------------------------------
# Request / Response Models
# -----------------------------------------------------

class RevealDecisionIn(BaseModel):
    conversation_id: str
    other_user_id: str
    decision: Decision


class RevealDecisionOut(BaseModel):
    status: str
    ai_message: Optional[str] = None
    slot: int
    day_key: str


# -----------------------------------------------------
# Helpers
# -----------------------------------------------------

def _pair_low_high(a, b):
    a = str(a)
    b = str(b)
    return (a, b) if a < b else (b, a)


def _is_blocked(db: Session, a: str, b: str) -> bool:
    low, high = _pair_low_high(a, b)
    row = db.execute(
        text("""
            select 1 from public.reveal_blocklist_v2
            where user_low = :low and user_high = :high
        """),
        {"low": low, "high": high},
    ).first()
    return row is not None


def _insert_block(db: Session, a: str, b: str, reason: str, cid: str):
    low, high = _pair_low_high(a, b)
    db.execute(
        text("""
            insert into public.reveal_blocklist_v2
                (user_low, user_high, reason, last_conversation_id)
            values (:low, :high, :reason, :cid)
            on conflict (user_low, user_high)
            do update set
                reason = excluded.reason,
                last_conversation_id = excluded.last_conversation_id
        """),
        {"low": low, "high": high, "reason": reason, "cid": cid},
    )


def _ensure_daily_slot(db: Session, viewer_id: str, target_id: str, cid: str):
    today = datetime.now().date()

    # Already exists?
    existing = db.execute(
        text("""
            select slot from public.reveal_daily_cycle_v2
            where viewer_id=:viewer_id
              and day_key=:day_key
              and target_id=:target_id
        """),
        {"viewer_id": viewer_id, "day_key": today, "target_id": target_id},
    ).first()

    if existing:
        return existing[0], today

    # Count used
    used = db.execute(
        text("""
            select slot from public.reveal_daily_cycle_v2
            where viewer_id=:viewer_id and day_key=:day_key
        """),
        {"viewer_id": viewer_id, "day_key": today},
    ).fetchall()

    used_slots = {u[0] for u in used}

    for slot in (1, 2, 3):
        if slot not in used_slots:
            db.execute(
                text("""
                    insert into public.reveal_daily_cycle_v2
                        (viewer_id, day_key, slot, target_id, conversation_id)
                    values (:viewer_id, :day_key, :slot, :target_id, :cid)
                """),
                {
                    "viewer_id": viewer_id,
                    "day_key": today,
                    "slot": slot,
                    "target_id": target_id,
                    "cid": cid,
                },
            )
            return slot, today

    raise HTTPException(
        status_code=429,
        detail="Daily cycle limit reached (3). Revisit today’s 3."
    )


# -----------------------------------------------------
# Main Endpoint
# -----------------------------------------------------

@router.post("/decision", response_model=RevealDecisionOut)
def reveal_decision_v2(
    payload: RevealDecisionIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if payload.other_user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot decide on self")

    # Block check
    if _is_blocked(db, user_id, payload.other_user_id):
        return RevealDecisionOut(
            status="search_next",
            ai_message="Already handled. Showing someone new.",
            slot=1,
            day_key=str(datetime.now().date())
        )

    slot, today = _ensure_daily_slot(
        db,
        viewer_id=user_id,
        target_id=payload.other_user_id,
        cid=payload.conversation_id,
    )

    # Store decision
    db.execute(
        text("""
            insert into public.reveal_decisions_v2
                (conversation_id, user_id, other_user_id, decision)
            values (:cid, :uid, :oid, :decision)
            on conflict (conversation_id, user_id)
            do update set decision=excluded.decision
        """),
        {
            "cid": payload.conversation_id,
            "uid": user_id,
            "oid": payload.other_user_id,
            "decision": payload.decision,
        },
    )

    # 🔎 CHECK OTHER USER DECISION
    other = db.execute(
        text("""
            select decision from public.reveal_decisions_v2
            where conversation_id = :cid
              and user_id = :other_id
        """),
        {
            "cid": payload.conversation_id,
            "other_id": payload.other_user_id,
        },
    ).fetchone()

    # --------------------------------------------------
    # PASS
    # --------------------------------------------------
    if payload.decision == "pass":
        _insert_block(db, user_id, payload.other_user_id, "passed", payload.conversation_id)
        db.commit()

        return RevealDecisionOut(
            status="search_next",
            ai_message="Not your vibe. Let’s find someone better matched.",
            slot=slot,
            day_key=str(today)
        )

    # --------------------------------------------------
    # MEET
    # --------------------------------------------------

    # Other user has not decided yet
    if not other:
        db.commit()
        return RevealDecisionOut(
            status="waiting",
            ai_message="Waiting for their response…",
            slot=slot,
            day_key=str(today)
        )

    # Other user passed
    if other[0] == "pass":
        _insert_block(db, user_id, payload.other_user_id, "passed", payload.conversation_id)
        db.commit()

        return RevealDecisionOut(
            status="search_next",
            ai_message="They weren’t aligned this time.",
            slot=slot,
            day_key=str(today)
        )

    # Both meet
    db.commit()
    return RevealDecisionOut(
        status="meeting",
        ai_message=None,
        slot=slot,
        day_key=str(today)
    )

@router.get("/media")
def reveal_media_v2(
    conversation_id: str,
    other_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rows = db.execute(
        text("""
            select id, media_type, file_path, is_primary
            from public.media_item
            where user_id = :uid
            order by is_primary desc, id asc
        """),
        {"uid": other_user_id},
    ).mappings().all()

    return {
        "media": [
            {
                "id": str(r["id"]),
                "media_type": r["media_type"],
                "url": r["file_path"],
                "is_primary": r["is_primary"],
            }
            for r in rows
        ]
    }