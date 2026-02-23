from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine

router = APIRouter(prefix="/v1", tags=["push"])


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
    schema: Optional[str] = None
    record: Dict[str, Any]
    old_record: Optional[Dict[str, Any]] = None


# ---------------------------
# Helpers
# ---------------------------

def _require_webhook_secret(x_webhook_secret: Optional[str]) -> None:
    expected = os.getenv("WEBHOOK_SECRET")
    if not expected:
        raise HTTPException(status_code=500, detail="WEBHOOK_SECRET not set on server")
    if not x_webhook_secret or x_webhook_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def _is_expo_token(token: str) -> bool:
    return token.startswith("ExponentPushToken[")


async def _send_expo_push(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    url = "https://exp.host/--/api/v2/push/send"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=messages)

        # Log response for debugging
        try:
            data = resp.json()
        except Exception:
            raise HTTPException(status_code=502, detail="Expo returned non-JSON response")

        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Expo push failed: {data}")

        return data


async def _supabase_get_conversation_participants(conversation_id: str) -> List[str]:
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        raise HTTPException(status_code=500, detail="SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")

    url = f"{supabase_url}/rest/v1/conversation_participants"
    params = {
        "conversation_id": f"eq.{conversation_id}",
        "select": "user_id"
    }

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=headers)

        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Supabase error: {resp.text}")

        rows = resp.json()
        return [r["user_id"] for r in rows if "user_id" in r]


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
    conversation_id = str(record.get("conversation_id", ""))
    sender_id = str(record.get("sender_id", ""))
    message_body = str(record.get("body", "") or "")

    if not conversation_id or not sender_id:
        return {"ok": True, "skipped": "missing conversation_id/sender_id"}

    participants = await _supabase_get_conversation_participants(conversation_id)

    targets = [uid for uid in participants if uid and uid != sender_id]

    if not targets:
        return {"ok": True, "skipped": "no targets"}

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
        "expo": result,
    }