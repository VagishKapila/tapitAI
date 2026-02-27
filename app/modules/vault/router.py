from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import os
import httpx

from app.db import get_db

router = APIRouter(prefix="/v1/vault", tags=["vault"])


async def _get_user_from_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth token")

    token = authorization.split(" ")[1]
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": service_key,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")

    return resp.json()["id"]


def _static(file_path: str) -> str:
    return f"/static{file_path}"


# -------------------------------
# GET VAULT HISTORY
# -------------------------------
@router.get("/history")
async def get_vault_history(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user_id = await _get_user_from_token(authorization)

    rows = db.execute(
        text("""
            select
                c.conversation_id,
                coalesce(o.outcome, 'pending') as outcome,
                cp2.user_id as other_user_id
            from public.conversation_decision c
            join public.conversation_decision cp2
              on c.conversation_id = cp2.conversation_id
             and cp2.user_id != :user_id
            left join public.conversation_outcome o
              on o.conversation_id = c.conversation_id
            where c.user_id = :user_id
            group by c.conversation_id, o.outcome, cp2.user_id
            order by max(c.created_at) desc
        """),
        {"user_id": user_id},
    ).mappings().all()

    history = []

    for r in rows:
        primary = db.execute(
            text("""
                select file_path
                from public.media_item
                where user_id = :other
                  and is_primary = true
                  and file_path is not null
                limit 1
            """),
            {"other": r["other_user_id"]},
        ).scalar()

        history.append({
            "conversation_id": r["conversation_id"],
            "other_user_id": r["other_user_id"],
            "outcome": r["outcome"],
            "primary_photo": _static(primary) if primary else None,
        })

    return history


# -------------------------------
# DELETE FROM VAULT
# -------------------------------
@router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user_id = await _get_user_from_token(authorization)

    db.execute(
        text("""
            delete from public.conversation_decision
            where conversation_id = :cid
              and user_id = :user_id
        """),
        {"cid": conversation_id, "user_id": user_id},
    )

    db.execute(
        text("""
            delete from public.conversation_outcome
            where conversation_id = :cid
        """),
        {"cid": conversation_id},
    )

    db.commit()

    return {"deleted": True}
