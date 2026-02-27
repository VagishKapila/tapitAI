from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class CyclePickResult:
    day_key: date
    slot: int
    target_id: str
    conversation_id: Optional[str]


def _pair_low_high(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a < b else (b, a)


def get_today_cycle_targets(db: Session, viewer_id: str, day_key: date) -> List[str]:
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


def get_today_cycle_count(db: Session, viewer_id: str, day_key: date) -> int:
    row = db.execute(
        text(
            """
            select count(*)::int as c
            from public.reveal_daily_cycle_v2
            where viewer_id = :viewer_id and day_key = :day_key
            """
        ),
        {"viewer_id": viewer_id, "day_key": day_key},
    ).mappings().first()
    return int(row["c"] if row and row.get("c") is not None else 0)


def is_blocked_pair(db: Session, user_a: str, user_b: str) -> bool:
    low, high = _pair_low_high(user_a, user_b)
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


def upsert_block_pair(db: Session, user_a: str, user_b: str, reason: str, conversation_id: Optional[str]) -> None:
    low, high = _pair_low_high(user_a, user_b)
    db.execute(
        text(
            """
            insert into public.reveal_blocklist_v2 (user_low, user_high, reason, last_conversation_id)
            values (:low, :high, :reason, :cid)
            on conflict (user_low, user_high)
            do update set
              reason = excluded.reason,
              last_conversation_id = coalesce(excluded.last_conversation_id, public.reveal_blocklist_v2.last_conversation_id)
            """
        ),
        {"low": low, "high": high, "reason": reason, "cid": conversation_id},
    )


def ensure_cycle_slot(
    db: Session,
    viewer_id: str,
    day_key: date,
    target_id: str,
    conversation_id: Optional[str],
) -> CyclePickResult:
    """
    Guarantees:
      - viewer has max 3 targets per day_key
      - if target already exists today => return its slot (no new slot consumed)
      - else assign next available slot 1..3 (or raise ValueError if full)
    """
    existing = db.execute(
        text(
            """
            select slot, conversation_id
            from public.reveal_daily_cycle_v2
            where viewer_id = :viewer_id and day_key = :day_key and target_id = :target_id
            """
        ),
        {"viewer_id": viewer_id, "day_key": day_key, "target_id": target_id},
    ).mappings().first()

    if existing:
        return CyclePickResult(
            day_key=day_key,
            slot=int(existing["slot"]),
            target_id=target_id,
            conversation_id=str(existing["conversation_id"]) if existing.get("conversation_id") else conversation_id,
        )

    # find next free slot
    used_slots = db.execute(
        text(
            """
            select slot
            from public.reveal_daily_cycle_v2
            where viewer_id = :viewer_id and day_key = :day_key
            """
        ),
        {"viewer_id": viewer_id, "day_key": day_key},
    ).mappings().all()

    used = {int(r["slot"]) for r in used_slots if r.get("slot") is not None}
    for slot in (1, 2, 3):
        if slot not in used:
            db.execute(
                text(
                    """
                    insert into public.reveal_daily_cycle_v2 (viewer_id, day_key, slot, target_id, conversation_id, status)
                    values (:viewer_id, :day_key, :slot, :target_id, :cid, 'active')
                    """
                ),
                {
                    "viewer_id": viewer_id,
                    "day_key": day_key,
                    "slot": slot,
                    "target_id": target_id,
                    "cid": conversation_id,
                },
            )
            return CyclePickResult(day_key=day_key, slot=slot, target_id=target_id, conversation_id=conversation_id)

    raise ValueError("daily_cycle_full")


def record_decision(
    db: Session,
    conversation_id: str,
    user_id: str,
    other_user_id: str,
    decision: str,  # 'meet' | 'pass'
) -> None:
    db.execute(
        text(
            """
            insert into public.reveal_decisions_v2 (conversation_id, user_id, other_user_id, decision)
            values (:cid, :uid, :oid, :decision)
            on conflict (conversation_id, user_id)
            do update set
              decision = excluded.decision,
              other_user_id = excluded.other_user_id,
              created_at = now()
            """
        ),
        {"cid": conversation_id, "uid": user_id, "oid": other_user_id, "decision": decision},
    )


def update_cycle_status(
    db: Session,
    viewer_id: str,
    day_key: date,
    target_id: str,
    status: str,  # 'passed' | 'meet' | 'active'
) -> None:
    db.execute(
        text(
            """
            update public.reveal_daily_cycle_v2
            set status = :status,
                updated_at = now()
            where viewer_id = :viewer_id and day_key = :day_key and target_id = :target_id
            """
        ),
        {"status": status, "viewer_id": viewer_id, "day_key": day_key, "target_id": target_id},
    )
