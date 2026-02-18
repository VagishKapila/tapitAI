import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.supabase_admin import supabase_admin
from app.services.expo_push import send_expo_push

router = APIRouter(prefix="/v1/nudge", tags=["nudge"])

MAX_ACTIVE = int(os.environ.get("MAX_ACTIVE_CONVERSATIONS_PER_USER", "1"))

class CreateNudgeIn(BaseModel):
    self_id: str
    other_user_id: str

class CreateNudgeOut(BaseModel):
    conversation_id: str
    status: str

class DecideIn(BaseModel):
    conversation_id: str
    user_id: str
    decision: str  # 'accept' | 'decline'

class DecideOut(BaseModel):
    conversation_id: str
    status: str
    matched: bool
    prefill: Optional[str] = None

async def _get_push_token(user_id: str) -> Optional[str]:
    sb = supabase_admin()
    res = sb.table("profiles").select("push_token").eq("id", user_id).maybe_single().execute()
    if not res.data:
        return None
    return res.data.get("push_token")

async def _push(user_id: str, title: str, body: str, data: dict) -> None:
    token = await _get_push_token(user_id)
    if token:
        await send_expo_push(token, title=title, body=body, data=data)

def _active_count(user_id: str) -> int:
    sb = supabase_admin()
    res = (
        sb.table("v_active_conversations")
        .select("conversation_id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return int(res.count or 0)

@router.post("/create", response_model=CreateNudgeOut)
async def create_nudge(payload: CreateNudgeIn):
    if payload.self_id == payload.other_user_id:
        raise HTTPException(status_code=400, detail="cannot nudge self")

    # Enforce "1 active chat" (easy to change via env)
    if _active_count(payload.self_id) >= MAX_ACTIVE:
        raise HTTPException(status_code=409, detail="max active conversations reached")
    if _active_count(payload.other_user_id) >= MAX_ACTIVE:
        raise HTTPException(status_code=409, detail="other user already busy")

    sb = supabase_admin()

    # Create conversation
    convo = sb.table("conversations").insert({
        "status": "nudged",
        "nudged_by": payload.self_id,
    }).select("id,status").single().execute()

    if not convo.data:
        raise HTTPException(status_code=500, detail="failed to create conversation")

    conversation_id = convo.data["id"]

    # Participants
    sb.table("conversation_participants").insert([
        {"conversation_id": conversation_id, "user_id": payload.self_id},
        {"conversation_id": conversation_id, "user_id": payload.other_user_id},
    ]).execute()

    # Wingman nudge message (AI/system)
    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "sender_id": payload.self_id,
        "body": "👋 Wingman nudge: I think you two should connect. Say hi 🙂",
    }).execute()

    # Push OTHER user: "You got a nudge"
    await _push(
        payload.other_user_id,
        title="TapIn Wingman",
        body="Someone nearby got nudged to say hi 👀",
        data={"type": "nudge", "conversationId": conversation_id},
    )

    return CreateNudgeOut(conversation_id=conversation_id, status="nudged")

@router.post("/decide", response_model=DecideOut)
async def decide(payload: DecideIn):
    if payload.decision not in ("accept", "decline"):
        raise HTTPException(status_code=400, detail="decision must be accept|decline")

    sb = supabase_admin()

    # Record decision (upsert)
    sb.table("conversation_acceptances").upsert({
        "conversation_id": payload.conversation_id,
        "user_id": payload.user_id,
        "decision": payload.decision,
    }).execute()

    # If anyone declines -> close it (optional: you can keep history)
    if payload.decision == "decline":
        sb.table("conversations").update({"status": "closed"}).eq("id", payload.conversation_id).execute()
        return DecideOut(conversation_id=payload.conversation_id, status="closed", matched=False, prefill=None)

    # Check accept count = 2
    acc = (
        sb.table("conversation_acceptances")
        .select("user_id,decision")
        .eq("conversation_id", payload.conversation_id)
        .execute()
    )
    accepts = [r for r in (acc.data or []) if r.get("decision") == "accept"]
    matched = len(accepts) >= 2

    if matched:
        # Mark matched
        sb.table("conversations").update({"status": "matched"}).eq("id", payload.conversation_id).execute()

        # Find both users
        parts = (
            sb.table("conversation_participants")
            .select("user_id")
            .eq("conversation_id", payload.conversation_id)
            .execute()
        )
        user_ids = [p["user_id"] for p in (parts.data or [])]

        prefill = "Hey 🙂 — Wingman says we’re both down. What are you up to right now?"

        # Push both: open chat
        for uid in user_ids:
            await _push(
                uid,
                title="It’s a match 🔥",
                body="Both said “Go for it” — say hi!",
                data={"type": "match", "conversationId": payload.conversation_id, "prefill": prefill},
            )

        return DecideOut(conversation_id=payload.conversation_id, status="matched", matched=True, prefill=prefill)

    return DecideOut(conversation_id=payload.conversation_id, status="nudged", matched=False, prefill=None)
