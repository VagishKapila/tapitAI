from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel


MediaType = Literal["image", "video"]


class PulseMedia(BaseModel):
    type: MediaType
    file_path: str  # e.g. "/uploads/<id>.jpeg" or "/uploads/<id>.mp4"


class PulseUser(BaseModel):
    user_id: str
    edge: str
    badges: List[str]
    media: List[PulseMedia]


class PulseCurrentResponse(BaseModel):
    wave_id: str
    ends_at: str  # ISO string
    viewer_count_estimate: int
    vote_count: int
    user: Optional[PulseUser] = None
