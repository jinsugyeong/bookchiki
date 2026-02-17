from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.recommendation import (
    RecommendationListResponse,
    RecommendationResponse,
    SearchResponse,
    SearchResultItem,
    IndexStatusResponse,
)
from app.services.recommend import get_recommendations
from app.services.rag import search_books_hybrid, index_all_books, index_book

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationListResponse)
async def get_my_recommendations(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get personalized book recommendations based on reading history and ratings."""
    results = await get_recommendations(db, current_user.id, limit=limit)
    return RecommendationListResponse(
        recommendations=[_to_response(r) for r in results],
        total=len(results),
    )


@router.post("/refresh", response_model=RecommendationListResponse)
async def refresh_recommendations(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force refresh recommendations (ignores cache)."""
    results = await get_recommendations(
        db, current_user.id, limit=limit, force_refresh=True
    )
    return RecommendationListResponse(
        recommendations=[_to_response(r) for r in results],
        total=len(results),
    )


def _to_response(r: dict) -> RecommendationResponse:
    """추천 dict를 RecommendationResponse로 변환."""
    return RecommendationResponse(
        book_id=UUID(r["book_id"]),
        title=r["title"],
        author=r["author"],
        description=r.get("description", ""),
        genre=r.get("genre", ""),
        cover_image_url=r.get("cover_image_url", ""),
        mood=r.get("mood", ""),
        score=r["score"],
        reason=r["reason"],
    )


search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.get("/natural", response_model=SearchResponse)
async def natural_language_search(
    q: str = Query(..., description="Natural language search query"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search books using natural language (hybrid keyword + vector search).

    결과가 부실하면 알라딘 API로 보완 검색하여 인덱스에 추가 후 재검색.
    Examples: "자기계발인데 너무 뻔하지 않은 책", "우울할 때 읽기 좋은 소설"
    """
    results = await search_books_hybrid(
        q, db=db, user_id=current_user.id, limit=limit,
    )
    return SearchResponse(
        results=[
            SearchResultItem(
                book_id=UUID(r["book_id"]),
                title=r["title"],
                author=r["author"],
                description=r.get("description", ""),
                genre=r.get("genre", ""),
                score=r["score"],
            )
            for r in results
        ],
        total=len(results),
        query=q,
    )


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/index-books", response_model=IndexStatusResponse)
async def index_all_books_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Index all books in OpenSearch (admin operation). Generates embeddings and indexes them."""
    count = await index_all_books(db)
    return IndexStatusResponse(
        indexed_count=count,
        message=f"Successfully indexed {count} books in OpenSearch.",
    )
