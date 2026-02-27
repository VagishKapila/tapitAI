from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import update
from uuid import UUID

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.db import models

router = APIRouter()



print("REVEAL V2 ROUTER ACTIVE")
class RevealDecisionRequest(BaseModel):
    conversation_id: UUID
    other_user_id: UUID
    decision: str  # "accept" or "pass"


@router.post("/v1/reveal/decision")
def reveal_decision(
    payload: RevealDecisionRequest,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    user_id = current_user_id

    if payload.decision not in ("accept", "pass"):
        raise HTTPException(status_code=400, detail="Invalid decision")

    # 1️⃣ Ensure conversation exists
    convo = db.query(models.Conversation).filter(
        models.Conversation.id == payload.conversation_id
    ).first()

    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if user_id not in (convo.user_a, convo.user_b):
        raise HTTPException(status_code=403, detail="Not part of conversation")

    # 2️⃣ Insert or update decision
    existing = db.query(models.RevealDecision).filter(
        models.RevealDecision.conversation_id == payload.conversation_id,
        models.RevealDecision.user_id == user_id,
    ).first()

    if existing:
        existing.decision = payload.decision
    else:
        decision_row = models.RevealDecision(
            conversation_id=payload.conversation_id,
            user_id=user_id,
            decision=payload.decision,
        )
        db.add(decision_row)

    db.commit()

    # 3️⃣ Fetch all decisions
    decisions = db.query(models.RevealDecision).filter(
        models.RevealDecision.conversation_id == payload.conversation_id
    ).all()

    # If only one responded
    if len(decisions) < 2:
        return {"status": "waiting"}

    # 4️⃣ Evaluate outcome
    decision_values = [d.decision for d in decisions]

    if all(d == "accept" for d in decision_values):
        db.execute(
            update(models.Conversation)
            .where(models.Conversation.id == payload.conversation_id)
            .values(status="matched", photos_revealed=True)
        )
        db.commit()

        return {
            "status": "matched",
            "conversation_id": str(payload.conversation_id),
        }

    # Someone passed
    db.execute(
        update(models.Conversation)
        .where(models.Conversation.id == payload.conversation_id)
        .values(status="passed")
    )
    db.commit()

    return {"status": "no_match"}