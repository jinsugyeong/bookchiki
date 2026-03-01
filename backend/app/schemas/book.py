import uuid
from datetime import date, datetime

from pydantic import BaseModel


class BookCreate(BaseModel):
    title: str
    author: str
    isbn: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    genre: str | None = None
    publisher: str | None = None
    published_at: date | None = None


class BookResponse(BaseModel):
    id: uuid.UUID
    title: str
    author: str
    isbn: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    genre: str | None = None
    publisher: str | None = None
    published_at: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BookSearchResult(BaseModel):
    title: str
    author: str
    isbn: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    genre: str | None = None
    publisher: str | None = None
    published_at: date | None = None
