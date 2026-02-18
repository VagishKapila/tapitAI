from pydantic import BaseModel
from typing import Optional, List

class PresenceHeartbeatRequest(BaseModel):
    lat: float
    lng: float
    venue_type: Optional[str] = None
    is_stationary: bool = True

class PresenceNearbyRequest(BaseModel):
    lat: float
    lng: float
    radius_miles: float = 1.0

class PresenceUser(BaseModel):
    user_id: str
    lat: float
    lng: float
    venue_type: Optional[str]

class PresenceNearbyResponse(BaseModel):
    users: List[PresenceUser]
