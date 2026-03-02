from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, Any

from app.db.session import get_db
from app.core.auth import get_current_user_id
from .service import get_full_settings, update_profile, update_settings

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class ProfileUpdate(BaseModel):
    # public.profiles fields
    display_name: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    interested_in: Optional[str] = None
    date_of_birth: Optional[str] = None

    # public.profile fields (extended onboarding)
    height_inches: Optional[int] = None
    height_preferences: Optional[Any] = None  # json list or structure
    intent: Optional[str] = None
    wingman_style: Optional[str] = None
    lifestyle_tags: Optional[list[str]] = None
    note_text: Optional[str] = None


class SettingsUpdate(BaseModel):
    ai_tone: Optional[str] = None
    auto_nudge: Optional[bool] = None
    notify_new_match: Optional[bool] = None
    notify_new_message: Optional[bool] = None
    notify_daily_reveal: Optional[bool] = None
    delayed_response_enabled: Optional[bool] = None
    delayed_response_minutes: Optional[int] = None


@router.get("/")
def get_settings(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return get_full_settings(db, user_id)


@router.put("/profile")
def put_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    data = payload.model_dump(exclude_unset=True)
    update_profile(db, user_id, data)
    return {"status": "ok"}


@router.put("/")
def put_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    data = payload.model_dump(exclude_unset=True)
    update_settings(db, user_id, data)
    return {"status": "ok"}