from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.db import get_db

from .service import get_current_pulse, cast_vote
from .schemas import PulseCurrentResponse


router = APIRouter(prefix="/v1/pulse", tags=["pulse"])


@router.get("/current", response_model=PulseCurrentResponse)
def pulse_current(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return get_current_pulse(db, str(user_id))


class VoteRequest(BaseModel):
    wave_id: str
    target_user_id: str


@router.post("/vote")
def pulse_vote(
    body: VoteRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        cast_vote(db, str(user_id), body.wave_id, body.target_user_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
