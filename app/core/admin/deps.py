from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.core.auth import get_current_user_id


def require_admin(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    row = db.execute(
        text("select is_admin from public.app_users where user_id = :uid"),
        {"uid": str(user_id)},
    ).mappings().first()

    if not row or not row["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required.")

    return str(user_id)
