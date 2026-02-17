import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.book import BookResponse


class UserBookCreate(BaseModel):
    book_id: uuid.UUID
    status: str = "wishlist"  # reading / read / wishlist
    rating: int | None = Field(None, ge=1, le=5)
    memo: str | None = None
    started_at: date | None = None
    finished_at: date | None = None


class UserBookUpdate(BaseModel):
    status: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    memo: str | None = None
    started_at: date | None = None
    finished_at: date | None = None


class UserBookResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    status: str
    rating: int | None = None
    memo: str | None = None
    started_at: date | None = None
    finished_at: date | None = None
    source: str
    created_at: datetime
    book: BookResponse | None = None

    model_config = {"from_attributes": True}


class ReadingStats(BaseModel):
    total_books: int
    books_read: int
    books_reading: int
    books_wishlist: int
    average_rating: float | None
    genre_distribution: dict[str, int]
    monthly_counts: dict[str, int]
