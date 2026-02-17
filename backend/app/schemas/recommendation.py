import uuid
from datetime import datetime

from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    book_id: uuid.UUID
    title: str
    author: str
    description: str = ""
    genre: str = ""
    cover_image_url: str = ""
    mood: str = ""
    score: float
    reason: str

    model_config = {"from_attributes": True}


class RecommendationListResponse(BaseModel):
    recommendations: list[RecommendationResponse]
    total: int


class SearchResultItem(BaseModel):
    book_id: uuid.UUID
    title: str
    author: str
    description: str = ""
    genre: str = ""
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int
    query: str


class IndexStatusResponse(BaseModel):
    indexed_count: int
    message: str
