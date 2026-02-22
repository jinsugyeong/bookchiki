import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


# ── Ask (질문 기반 추천) ──────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(5, ge=1, le=20)


class AskResultItem(BaseModel):
    title: str
    author: str
    reason: str
    isbn: str = ""
    cover_image_url: str = ""
    genre: str = ""


class AskResponse(BaseModel):
    results: list[AskResultItem]
    total: int
    question: str


# ── 취향 프로필 조회 ──────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    profile_data: Any | None
    is_dirty: bool
    updated_at: datetime | None


# ── 어드민 파이프라인 결과 ──────────────────────────────────────────────────────

class PipelineStatusResponse(BaseModel):
    total: int
    indexed: int
    skipped: int
    errors: int
    source_stats: dict = {}


class SeedStatusResponse(BaseModel):
    total: int
    seeded: int
    skipped: int
    errors: int
