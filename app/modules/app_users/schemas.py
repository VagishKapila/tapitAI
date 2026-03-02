from pydantic import BaseModel
from typing import Optional

class EnsureUserRequest(BaseModel):
    phone: Optional[str] = None

class AgeRequest(BaseModel):
    age: int
