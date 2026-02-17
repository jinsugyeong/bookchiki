import uuid
from datetime import datetime

from pydantic import BaseModel


class HighlightCreate(BaseModel):
    user_book_id: uuid.UUID
    content: str
    page_number: int | None = None
    note: str | None = None
    color: str = "yellow"


class HighlightUpdate(BaseModel):
    content: str | None = None
    page_number: int | None = None
    note: str | None = None
    color: str | None = None


class HighlightResponse(BaseModel):
    id: uuid.UUID
    user_book_id: uuid.UUID
    content: str
    page_number: int | None = None
    note: str | None = None
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}
