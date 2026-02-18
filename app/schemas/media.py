from pydantic import BaseModel, Field
from typing import List

class MediaItemPayload(BaseModel):
    id: str
    media_type: str = Field(..., pattern="^(image|video)$")
    order_index: int
    is_primary: bool = False

class MediaBatchRequest(BaseModel):
    items: List[MediaItemPayload] = Field(..., min_items=1)
