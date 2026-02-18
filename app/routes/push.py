from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
import requests

from app.core.db import get_db
from app.models.push_token import PushToken

router = APIRouter(prefix="/push", tags=["push"])


class RegisterTokenRequest(BaseModel):
    user_id: str
    expo_token: str


@router.post("/register")
def register_push_token(data: RegisterTokenRequest, db: Session = Depends(get_db)):
    existing = db.query(PushToken).filter(
        PushToken.expo_token == data.expo_token
    ).first()

    if existing:
        return {"status": "already_registered"}

    token = PushToken(
        id=str(uuid.uuid4()),
        user_id=data.user_id,
        expo_token=data.expo_token
    )

    db.add(token)
    db.commit()
    return {"status": "registered"}


@router.post("/test")
def send_test_push(user_id: str, db: Session = Depends(get_db)):
    tokens = db.query(PushToken).filter(
        PushToken.user_id == user_id
    ).all()

    messages = []
    for token in tokens:
        messages.append({
            "to": token.expo_token,
            "sound": "default",
            "title": "TapItAI Test 🚀",
            "body": "Push notifications are working."
        })

    response = requests.post(
        "https://exp.host/--/api/v2/push/send",
        json=messages
    )

    return {
        "sent_to": len(messages),
        "expo_response": response.json()
    }
