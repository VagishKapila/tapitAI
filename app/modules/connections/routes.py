from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from .service import (
    request_connection,
    accept_connection,
    reject_connection,
    send_message,
    get_messages,
)

router = APIRouter(prefix="/v1/connect", tags=["connections"])


@router.post("/request")
def connect_request(
    payload: dict,
    x_user_id: str = Header(...),
    db: Session = Depends(get_db),
):
    target_id = payload.get("target_user_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="target_user_id required")

    try:
        conn = request_connection(db, x_user_id, target_id)
        return {"connection_id": conn.id, "status": conn.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/accept")
def connect_accept(
    payload: dict,
    x_user_id: str = Header(...),
    db: Session = Depends(get_db),
):
    try:
        convo = accept_connection(db, payload["connection_id"], x_user_id)
        return {"conversation_id": convo.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reject")
def connect_reject(
    payload: dict,
    x_user_id: str = Header(...),
    db: Session = Depends(get_db),
):
    try:
        conn = reject_connection(db, payload["connection_id"], x_user_id)
        return {"status": conn.status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/message/send")
def message_send(
    payload: dict,
    x_user_id: str = Header(...),
    db: Session = Depends(get_db),
):
    try:
        msg = send_message(
            db,
            payload["conversation_id"],
            x_user_id,
            payload["body"],
        )
        return {"message_id": msg.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/message/{conversation_id}")
def message_list(
    conversation_id: int,
    x_user_id: str = Header(...),
    db: Session = Depends(get_db),
):
    msgs = get_messages(db, conversation_id)
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "body": m.body,
            "created_at": m.created_at,
        }
        for m in msgs
    ]
