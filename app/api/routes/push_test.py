from fastapi import APIRouter
import requests
from pydantic import BaseModel

router = APIRouter(prefix="/push", tags=["push"])


class PushTestRequest(BaseModel):
    token: str
    title: str
    body: str


@router.post("/test")
def send_test_push(payload: PushTestRequest):
    response = requests.post(
        "https://exp.host/--/api/v2/push/send",
        json={
            "to": payload.token,
            "title": payload.title,
            "body": payload.body,
            "sound": "default",
        },
        headers={"Content-Type": "application/json"},
    )

    return {"expo_response": response.json()}
