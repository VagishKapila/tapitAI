# backend/app/api/push.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine

router = APIRouter(prefix="/v1", tags=["push"])

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


# ---------------------------
# Models
# ---------------------------

class RegisterPushTokenIn(BaseModel):
    user_id: str
    expo_push_token: str
    platform: Optional[str] = None
    device_id: Optional[str] = None


class SupabaseWebhookPayload(BaseModel):
    type: Optional[str] = None
    table: Optional[str] = None

    # avoid pydantic warning about "schema" shadowing BaseModel attr
    schema_: Optional[str] = Field(default=None, alias="schema")

    record: Dict[str, Any]
    old_record: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


# ---------------------------
# Helpers (auth / validation)
# ---------------------------

def _require_webhook_secret(x_webhook_secret: Optional[str]) -> None:
    expected = os.getenv("WEBHOOK_SECRET")
    if not expected:
        raise HTTPException(status_code=500, detail="WEBHOOK_SECRET not set on server")
    if not x_webhook_secret or x_webhook_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def _is_expo_token(token: str) -> bool:
    return token.startswith("ExponentPushToken[")


def _supabase_headers(service_key: str) -> Dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        # keep response small
        "Accept": "application/json",
    }


def _get_supabase_env() -> Tuple[str, str]:
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set",
        )

    return supabase_url.rstrip("/"), service_key


# ---------------------------
# Helpers (expo push)
# ---------------------------

async def _send_expo_push(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(EXPO_PUSH_URL, json=messages)

        try:
            data = resp.json()
        except Exception:
            raise HTTPException(status_code=502, detail="Expo returned non-JSON response")

        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Expo push failed: {data}")

        return data


# ---------------------------
# Helpers (supabase reads)
# ---------------------------

async def _supabase_get_conversation_participants(conversation_id: str) -> List[str]:
    supabase_url, service_key = _get_supabase_env()

    url = f"{supabase_url}/rest/v1/conversation_participants"
    params = {"conversation_id": f"eq.{conversation_id}", "select": "user_id"}
    headers = _supabase_headers(service_key)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Supabase error: {resp.text}")

        rows = resp.json()
        return [r["user_id"] for r in rows if "user_id" in r]


async def _supabase_get_distinct_senders(conversation_id: str) -> Set[str]:
    """
    Messages live in Supabase. Local Postgres does NOT have them.
    We count distinct sender_id values for the conversation via Supabase REST.
    """
    supabase_url, service_key = _get_supabase_env()

    url = f"{supabase_url}/rest/v1/messages"
    # only fetch sender_id to keep payload small
    params = {"conversation_id": f"eq.{conversation_id}", "select": "sender_id"}
    headers = _supabase_headers(service_key)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code >= 400:
            # don't crash the webhook; just treat as not revealed yet
            return set()

        rows = resp.json()
        return {r["sender_id"] for r in rows if "sender_id" in r and r["sender_id"]}


# ---------------------------
# Helpers (local DB: push tokens)
# ---------------------------

def _get_tokens_for_user(engine: Engine, user_id: str) -> List[Dict[str, Any]]:
    q = text("""
        select expo_push_token, platform, device_id
        from public.push_tokens
        where user_id = :user_id
        order by updated_at desc
    """)

    with engine.begin() as conn:
        rows = conn.execute(q, {"user_id": user_id}).mappings().all()

    return [dict(r) for r in rows]


def _upsert_token(engine: Engine, payload: RegisterPushTokenIn) -> None:
    with engine.begin() as conn:
        if payload.device_id:
            conn.execute(
                text("""
                    insert into public.push_tokens (user_id, expo_push_token, platform, device_id)
                    values (:user_id, :expo_push_token, :platform, :device_id)
                    on conflict (user_id, device_id)
                    do update set
                        expo_push_token = excluded.expo_push_token,
                        platform = excluded.platform,
                        updated_at = now()
                """),
                payload.model_dump(),
            )
        else:
            conn.execute(
                text("""
                    insert into public.push_tokens (user_id, expo_push_token, platform)
                    values (:user_id, :expo_push_token, :platform)
                """),
                payload.model_dump(),
            )


# ---------------------------
# Helpers (local DB: reveal state)
# ---------------------------

def _local_mark_revealed(
    engine: Engine,
    conversation_id: str,
    requester_id: str,
    target_id: str,
) -> None:
    """
    We store reveal state locally in public.connections.

    IMPORTANT: We set connections.id = conversation_id (UUID).
    That way you can query reveal state by conversation_id without adding new columns.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into public.connections (id, requester_id, target_id, status, revealed_at)
                values (:id, :requester_id, :target_id, 'accepted', now())
                on conflict (id)
                do update set
                    revealed_at = coalesce(public.connections.revealed_at, excluded.revealed_at),
                    status = excluded.status
            """),
            {
                "id": conversation_id,
                "requester_id": requester_id,
                "target_id": target_id,
            },
        )


def _local_is_revealed(engine: Engine, conversation_id: str) -> bool:
    with engine.begin() as conn:
        row = conn.execute(
            text("select revealed_at from public.connections where id = :id"),
            {"id": conversation_id},
        ).mappings().first()

    if not row:
        return False
    return row.get("revealed_at") is not None


async def _maybe_reveal_after_two_senders(
    engine: Engine,
    conversation_id: str,
    participants: List[str],
) -> bool:
    """
    Reveal rule v1:
      - conversation has at least 2 distinct sender_ids in Supabase messages table
      - then mark revealed locally (public.connections.revealed_at)

    Returns: True if revealed now (or already revealed), else False
    """
    if _local_is_revealed(engine, conversation_id):
        return True

    distinct_senders = await _supabase_get_distinct_senders(conversation_id)
    if len(distinct_senders) < 2:
        return False

    # Use first two participants as requester/target (stable + simple for v1)
    # participants are UUID strings
    if len(participants) < 2:
        return False

    requester_id = participants[0]
    target_id = participants[1]

    import asyncio
    await asyncio.sleep(2)

    _local_mark_revealed(engine, conversation_id, requester_id, target_id)
    return True


# ---------------------------
# Routes
# ---------------------------


@router.post("/push/register")
async def register_push_token(
    body: RegisterPushTokenIn,
    engine: Engine = Depends(get_engine),
):
    if not _is_expo_token(body.expo_push_token):
        raise HTTPException(status_code=400, detail="Invalid Expo push token")

    _upsert_token(engine, body)
    return {"ok": True}


@router.post("/webhooks/supabase/messages")
async def supabase_messages_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None),
    engine: Engine = Depends(get_engine),
):
    _require_webhook_secret(x_webhook_secret)

    # SAFE JSON PARSE (no more 500 crash)
    try:
        body_bytes = await request.body()
        if not body_bytes:
            return {"ok": True, "skipped": "empty body"}
        payload_json = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    payload = SupabaseWebhookPayload(**payload_json)

    record = payload.record or {}
    conversation_id = str(record.get("conversation_id", "") or "")
    sender_id = str(record.get("sender_id", "") or "")
    message_body = str(record.get("body", "") or "")

    if not conversation_id or not sender_id:
        return {"ok": True, "skipped": "missing conversation_id/sender_id"}

    participants = await _supabase_get_conversation_participants(conversation_id)
    targets = [uid for uid in participants if uid and uid != sender_id]

    if not targets:
        return {"ok": True, "skipped": "no targets"}

    # 🔥 Reveal check uses Supabase messages, then writes reveal state locally
    revealed = await _maybe_reveal_after_two_senders(engine, conversation_id, participants)

    expo_messages: List[Dict[str, Any]] = []

    for target_user_id in targets:
        tokens = _get_tokens_for_user(engine, target_user_id)

        for t in tokens:
            token = t.get("expo_push_token")
            if not token:
                continue

            expo_messages.append(
                {
                    "to": token,
                    "sound": "default",
                    "title": "TapIn",
                    "body": message_body[:120] if message_body else "New message",
                    "data": {
                        "type": "chat_message",
                        "conversationId": conversation_id,
                        "senderId": sender_id,
                        # ✅ front-end can use this to decide whether to fetch profile media
                        "revealReady": revealed,
                    },
                    "priority": "high",
                }
            )

    if not expo_messages:
        return {"ok": True, "skipped": "no registered tokens for targets"}

    result = await _send_expo_push(expo_messages)

    return {
        "ok": True,
        "sent": len(expo_messages),
        "reveal_ready": revealed,
        "expo": result,
    }

@router.get("/reveal/profile")
def get_revealed_profile(
    conversation_id: str,
    other_user_id: str,
    engine: Engine = Depends(get_engine),
):
    # 1️⃣ Check reveal state
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                select revealed_at
                from public.connections
                where id = :id
            """),
            {"id": conversation_id},
        ).mappings().first()

    if not row or not row.get("revealed_at"):
        raise HTTPException(status_code=403, detail="Not revealed yet")

    # 2️⃣ Fetch primary media from local DB
    with engine.begin() as conn:
        media = conn.execute(
            text("""
                select id
                from public.media_item
                where user_id = :uid
                and is_primary = true
                limit 1
            """),
            {"uid": other_user_id},
        ).mappings().first()

    if not media:
        return {"primaryPhotoUrl": None}

    media_id = media["id"]

    return {
        "primaryPhotoUrl": f"/static/uploads/{media_id}.jpg"
    }
@router.post("/reveal/decision")
def reveal_decision(
    conversation_id: str,
    decision: str,
    engine: Engine = Depends(get_engine),
):
    if decision not in ["meet", "pass"]:
        raise HTTPException(status_code=400, detail="Invalid decision")

    with engine.begin() as conn:
        row = conn.execute(
            text("select decline_count from public.connections where id = :id"),
            {"id": conversation_id},
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Connection not found")

        if decision == "meet":
            conn.execute(
                text("""
                    update public.connections
                    set status = 'accepted'
                    where id = :id
                """),
                {"id": conversation_id},
            )
            return {"status": "meeting"}

        # PASS LOGIC
        new_decline = (row["decline_count"] or 0) + 1

        if new_decline >= 3:
            conn.execute(
                text("""
                    update public.connections
                    set status = 'expired'
                    where id = :id
                """),
                {"id": conversation_id},
            )
            return {"status": "ended"}

        conn.execute(
            text("""
                update public.connections
                set decline_count = :c,
                    status = 'rejected'
                where id = :id
            """),
            {"c": new_decline, "id": conversation_id},
        )

    return {"status": "search_next"}
