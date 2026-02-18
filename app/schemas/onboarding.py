from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.enums import (
    OnboardingStep,
    WingmanStyle,
    HeightPreference,
    IntentType,
    LocationPermission
)

# ---------- shared ----------
class OnboardingStateResponse(BaseModel):
    completed: bool
    current_step: OnboardingStep
    next_route: OnboardingStep | None = None


# ---------- start ----------
class OnboardingStartRequest(BaseModel):
    version: int = Field(..., example=1)


# ---------- location ----------
class OnboardingLocationRequest(BaseModel):
    permission: LocationPermission
    coarse_cell_id: Optional[str] = None


# ---------- prefs ----------
class OnboardingPrefsRequest(BaseModel):
    height_inches: int = Field(..., ge=48, le=96)
    height_preferences: List[HeightPreference]
    wingman_style: WingmanStyle


# ---------- intent ----------
class OnboardingIntentRequest(BaseModel):
    intent: IntentType


# ---------- lifestyle ----------
class OnboardingLifestyleRequest(BaseModel):
    tags: List[str]


# ---------- media ----------
class OnboardingMediaRequest(BaseModel):
    media_ids: List[str]


# ---------- note ----------
class OnboardingNoteRequest(BaseModel):
    note_text: Optional[str] = None


# ---------- complete ----------
class OnboardingCompleteRequest(BaseModel):
    version: int

class OnboardingLifestyleRequest(BaseModel):
    lifestyle_tags: list[str] = Field(..., min_items=1)


class OnboardingNoteRequest(BaseModel):
    note_text: str | None = None
