from datetime import datetime
from pydantic import BaseModel

class BaseSchema(BaseModel):
    class Config:
        from_attributes = True

class TimestampedSchema(BaseSchema):
    created_at: datetime | None = None
    updated_at: datetime | None = None
