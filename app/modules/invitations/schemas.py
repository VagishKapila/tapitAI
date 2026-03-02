from pydantic import BaseModel
from typing import Optional


class InviteValidateRequest(BaseModel):
    code: str
    user_id: str
    phone: Optional[str] = None


class InviteValidateResponse(BaseModel):
    success: bool
    message: str


class WaitlistRequestCreate(BaseModel):
    phone: str
    name: Optional[str] = None


class InviteCreateRequest(BaseModel):
    max_uses: int = 1
    expires_at: Optional[str] = None
    notes: Optional[str] = None


class InviteCodeResponse(BaseModel):
    id: str
    code: str
    max_uses: int
    used_count: int
    is_active: bool
    expires_at: Optional[str]
    created_at: Optional[str]
