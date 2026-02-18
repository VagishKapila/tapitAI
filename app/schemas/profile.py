from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.enums import WingmanStyle, HeightPreference, IntentType

class ProfileUpdateRequest(BaseModel):
    height_inches: Optional[int] = Field(None, ge=48, le=96)
    height_preferences: Optional[List[HeightPreference]]
    wingman_style: Optional[WingmanStyle]
    intent: Optional[IntentType]
    note_text: Optional[str]
