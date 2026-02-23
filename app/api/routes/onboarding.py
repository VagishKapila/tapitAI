from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import get_current_user_id

from app.models.onboarding import OnboardingState
from app.models.profile import Profile
from app.models.media import MediaItem

from app.schemas.onboarding import (
    OnboardingStartRequest,
    OnboardingLocationRequest,
    OnboardingPrefsRequest,
    OnboardingIntentRequest,
    OnboardingLifestyleRequest,
    OnboardingNoteRequest,
    OnboardingStateResponse,
)
from app.schemas.media import MediaBatchRequest
from app.schemas.enums import OnboardingStep

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ----------------------------
# START
# ----------------------------
@router.post("/start", response_model=OnboardingStateResponse)
def start_onboarding(
    payload: OnboardingStartRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),       
):
    logger.info(f"Onboarding start | user={user_id}")

    state = db.get(OnboardingState, user_id)
    if state:
        return OnboardingStateResponse(
            completed=state.completed,
            current_step=state.current_step,
            next_route=None if state.completed else state.current_step,
        )

    state = OnboardingState(
        user_id=user_id,
        version=payload.version,
        completed=False,
        current_step=OnboardingStep.location,
    )
    db.add(state)
    db.commit()

    return OnboardingStateResponse(
        completed=False,
        current_step=OnboardingStep.location,
        next_route=OnboardingStep.location,
    )


# ----------------------------
# LOCATION
# ----------------------------
@router.put("/location", response_model=OnboardingStateResponse)
def save_location(
    payload: OnboardingLocationRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    state = db.get(OnboardingState, user_id)
    if not state:
        raise HTTPException(status_code=400, detail="Onboarding not started")

    state.current_step = OnboardingStep.prefs
    db.commit()

    logger.info("Advanced to prefs")

    return OnboardingStateResponse(
        completed=False,
        current_step=state.current_step,
        next_route=OnboardingStep.prefs,
    )


# ----------------------------
# PREFS
# ----------------------------
@router.put("/prefs", response_model=OnboardingStateResponse)
def save_prefs(
    payload: OnboardingPrefsRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    state = db.get(OnboardingState, user_id)
    if not state:
        raise HTTPException(status_code=400, detail="Onboarding not started")

    profile = db.get(Profile, user_id) or Profile(user_id=user_id)
    profile.height_inches = payload.height_inches
    profile.height_preferences = payload.height_preferences
    profile.wingman_style = payload.wingman_style

    db.add(profile)
    state.current_step = OnboardingStep.intent
    db.commit()

    logger.info("Advanced to intent")

    return OnboardingStateResponse(
        completed=False,
        current_step=state.current_step,
        next_route=OnboardingStep.intent,
    )


# ----------------------------
# INTENT
# ----------------------------
@router.put("/intent", response_model=OnboardingStateResponse)
def save_intent(
    payload: OnboardingIntentRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    state = db.get(OnboardingState, user_id)
    if not state:
        raise HTTPException(status_code=400, detail="Onboarding not started")

    profile = db.get(Profile, user_id) or Profile(user_id=user_id)
    profile.intent = payload.intent

    db.add(profile)
    state.current_step = OnboardingStep.lifestyle
    db.commit()

    logger.info("Advanced to lifestyle")

    return OnboardingStateResponse(
        completed=False,
        current_step=state.current_step,
        next_route=OnboardingStep.lifestyle,
    )


# ----------------------------
# LIFESTYLE
# ----------------------------
@router.put("/lifestyle", response_model=OnboardingStateResponse)
def save_lifestyle(
    payload: OnboardingLifestyleRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    state = db.get(OnboardingState, user_id)
    if not state or state.current_step != OnboardingStep.lifestyle:
        raise HTTPException(status_code=400, detail="Invalid onboarding state")

    profile = db.get(Profile, user_id) or Profile(user_id=user_id)
    profile.lifestyle_tags = payload.lifestyle_tags

    db.add(profile)
    state.current_step = OnboardingStep.media
    db.commit()

    logger.info("Advanced to media")

    return OnboardingStateResponse(
        completed=False,
        current_step=state.current_step,
        next_route=OnboardingStep.media,
    )


# ----------------------------
# MEDIA
# ----------------------------
@router.put("/media", response_model=OnboardingStateResponse)
def save_media(
    payload: MediaBatchRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    state = db.get(OnboardingState, user_id)
    if not state or state.current_step != OnboardingStep.media:
        raise HTTPException(status_code=400, detail="Invalid onboarding state")

    db.query(MediaItem).filter(MediaItem.user_id == user_id).delete()

    for item in payload.items:
        db.add(
            MediaItem(
                user_id=user_id,
                media_type=item.media_type,
                order_index=item.order_index,
                is_primary=item.is_primary,
            )
        )

    state.current_step = OnboardingStep.note
    db.commit()

    logger.info("Advanced to note")

    return OnboardingStateResponse(
        completed=False,
        current_step=state.current_step,
        next_route=OnboardingStep.note,
    )


# ----------------------------
# NOTE → DONE
# ----------------------------
@router.put("/note", response_model=OnboardingStateResponse)
def save_note(
    payload: OnboardingNoteRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    state = db.get(OnboardingState, user_id)
    if not state or state.current_step != OnboardingStep.note:
        raise HTTPException(status_code=400, detail="Invalid onboarding state")

    if payload.note_text:
        profile = db.get(Profile, user_id) or Profile(user_id=user_id)
        profile.note_text = payload.note_text
        db.add(profile)

    state.completed = True
    state.completed_at = datetime.utcnow()
    state.current_step = OnboardingStep.done
    db.commit()

    logger.info("Onboarding completed")

    return OnboardingStateResponse(
        completed=True,
        current_step=OnboardingStep.done,
        next_route=None,
    )
