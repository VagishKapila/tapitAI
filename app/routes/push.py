from typing import Optional
from uuid import UUID

import requests
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import get_current_user_id
from app.models.push_token import PushToken

router = APIRouter(prefix="/push", tags=["push"])


# ----------------------------
# Schemas
# ----------------------------
class PushTestRequest(BaseModel):
    token: str
    title: str
    body: str


class PushRegisterRequest(BaseModel):
    token: str  # Expo push token


class PushSendRequest(BaseModel):
    to_user_id: UUID
    title: str
    body: str


# ----------------------------
# Helper: send to Expo
# ----------------------------
def _send_expo_push(expo_token: str, title: str, body: str) -> dict:
    url = "https://exp.host/--/api/v2/push/send"
    payload = {"to": expo_token, "title": title, "body": body, "sound": "default"}

    r = requests.post(url, json=payload, timeout=15)
    try:
        data = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail=f"Expo returned non-JSON: {r.text[:200]}")

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Expo push error: {data}")

    return data


# ----------------------------
# Existing: manual token test (curl)
# ----------------------------
@router.post("/test")
def push_test(payload: PushTestRequest):
    expo_resp = _send_expo_push(payload.token, payload.title, payload.body)
    return {"expo_response": expo_resp}


# ----------------------------
# NEW: Register token for current user
# ----------------------------
@router.post("/register")
def register_push_token(
    payload: PushRegisterRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    if not payload.token or "ExponentPushToken[" not in payload.token:
        raise HTTPException(status_code=400, detail="Invalid Expo push token format")

    row = db.get(PushToken, user_id)
    if row:
        row.expo_push_token = payload.token
    else:
        row = PushToken(user_id=user_id, expo_push_token=payload.token)
        db.add(row)

    db.commit()
    logger.info(f"Registered push token | user={user_id}")
    return {"ok": True}


# ----------------------------
# NEW: Send push to another user by user_id
# ----------------------------
@router.post("/send")
def send_push_to_user(
    payload: PushSendRequest,
    db: Session = Depends(get_db),
    sender_user_id: UUID = Depends(get_current_user_id),
):
    target = db.get(PushToken, payload.to_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target user has no registered push token")

    expo_resp = _send_expo_push(target.expo_push_token, payload.title, payload.body)
    logger.info(f"Push sent | from={sender_user_id} to={payload.to_user_id}")
    return {"ok": True, "expo_response": expo_resp}
