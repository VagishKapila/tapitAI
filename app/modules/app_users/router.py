from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user_id
from .schemas import EnsureUserRequest, AgeRequest
from .service import ensure_app_user, set_user_age

router = APIRouter(prefix="/v1/app_users", tags=["app_users"])


@router.post("/ensure")
def ensure_user(
    payload: EnsureUserRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    ensure_app_user(db, str(user_id), payload.phone)
    return {"status": "ok"}


@router.post("/set_age")
def set_age(
    payload: AgeRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    ok = set_user_age(db, str(user_id), payload.age)

    if not ok:
        raise HTTPException(
            status_code=403,
            detail="You must be 18 or older to use this app."
        )

    return {"status": "ok"}
