"""추천 API: 기록 기반 추천, 질문 기반 추천, 관리자 엔드포인트."""

import json
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, delete

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.book import Book
from app.models.user_dismissed_book import UserDismissedBook
from app.schemas.recommendation import (
    RecommendationListResponse,
    RecommendationResponse,
    AskRequest,
    AskResponse,
    AskResultItem,
    ProfileResponse,
    PipelineStatusResponse,
    SeedStatusResponse,
    IndexStatusResponse,
)
from app.services.recommend import get_recommendations
from app.services.rag import search_knowledge
from app.services.profile_cache import get_or_create_profile

logger = logging.getLogger(__name__)

_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationListResponse)
async def get_my_recommendations(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """기록 기반 개인화 도서 추천 (is_dirty 플래그로 캐시 관리)."""
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
    """추천 강제 재생성 (캐시 무시)."""
    results = await get_recommendations(
        db, current_user.id, limit=limit, force_refresh=True
    )
    return RecommendationListResponse(
        recommendations=[_to_response(r) for r in results],
        total=len(results),
    )


@router.post("/ask", response_model=AskResponse)
async def ask_recommendations(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """질문 기반 추천: 자연어 질문 + 취향 프로필 컨텍스트 → RAG 검색 → LLM 추천.

    DB 저장 없음, 추천 캐시 overwrite 없음.
    """
    # 1단계: 취향 프로필 조회 (is_dirty 무관)
    profile = await get_or_create_profile(db, current_user.id)
    profile_data = profile.profile_data or {}

    profile_context = _build_profile_context(profile_data)

    # 2단계: rag_knowledge 인덱스 하이브리드 검색
    rag_chunks = await search_knowledge(request.question, k=10)
    rag_context = _build_rag_context(rag_chunks)

    # 3단계: LLM 호출 (취향 프로필 + RAG 청크 컨텍스트)
    suggestions_raw = await _ask_llm(
        question=request.question,
        profile_context=profile_context,
        rag_context=rag_context,
        limit=request.limit,
    )

    if not suggestions_raw:
        return AskResponse(results=[], total=0, question=request.question)

    # 서재 + dismissed ISBN/book_id 수집 (제외용)
    from app.models.user_book import UserBook
    from app.models.user_dismissed_book import UserDismissedBook
    library_result = await db.execute(
        select(UserBook.book_id).where(UserBook.user_id == current_user.id)
    )
    library_book_ids = {str(r) for r in library_result.scalars().all()}
    dismissed_result = await db.execute(
        select(UserDismissedBook.book_id).where(UserDismissedBook.user_id == current_user.id)
    )
    dismissed_book_ids = {str(r) for r in dismissed_result.scalars().all()}
    exclude_ids = library_book_ids | dismissed_book_ids

    results = []
    for item in suggestions_raw:
        if len(results) >= request.limit:
            break
        title = item.get("title", "")
        author = item.get("author", "")
        book_info = await _find_or_save_book(db, title, author)

        # 서재/dismissed 책 제외
        bid = book_info.get("book_id", "")
        if bid and bid in exclude_ids:
            logger.info("[ask] 서재/dismissed 책 제외: '%s'", title)
            continue

        results.append(AskResultItem(
            title=book_info.get("title") or title,
            author=book_info.get("author") or author,
            reason=item.get("reason_hint", ""),
            book_id=bid,
            isbn=book_info.get("isbn", ""),
            cover_image_url=book_info.get("cover_image_url", ""),
            genre=book_info.get("genre", ""),
            description=book_info.get("description", ""),
        ))

    logger.info(
        "[ask] user=%s question='%s' results=%d",
        current_user.id, request.question, len(results),
    )

    return AskResponse(results=results, total=len(results), question=request.question)


@router.post("/dismiss/{book_id}", status_code=204)
async def dismiss_recommendation(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """추천 책 영구 비추천 처리 ('다른 책' 버튼).

    1. user_dismissed_books에 영구 저장
    2. recommendations 캐시에서 즉시 제거 → 새로고침해도 안 나옴
    멱등 처리 (이미 dismiss된 경우 무시).
    """
    from app.models.recommendation import Recommendation

    existing = await db.execute(
        select(UserDismissedBook).where(
            UserDismissedBook.user_id == current_user.id,
            UserDismissedBook.book_id == book_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(UserDismissedBook(user_id=current_user.id, book_id=book_id))

    # recommendations 캐시에서 즉시 삭제 (새로고침해도 복구 안됨)
    del_result = await db.execute(
        delete(Recommendation).where(
            Recommendation.user_id == current_user.id,
            Recommendation.book_id == book_id,
        )
    )

    await db.commit()

    # 검증 로그
    verify = await db.execute(
        select(UserDismissedBook).where(
            UserDismissedBook.user_id == current_user.id,
            UserDismissedBook.book_id == book_id,
        )
    )
    saved = verify.scalar_one_or_none()
    logger.info(
        "[dismiss] user=%s book=%s dismissed_saved=%s rec_deleted=%d",
        current_user.id, book_id, saved is not None, del_result.rowcount,
    )


@router.get("/profile", response_model=ProfileResponse)
async def get_preference_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 유저의 취향 프로필 조회."""
    profile = await get_or_create_profile(db, current_user.id)
    return ProfileResponse(
        profile_data=profile.profile_data,
        is_dirty=profile.is_dirty,
        updated_at=profile.updated_at,
    )


async def _find_or_save_book(db: AsyncSession, title: str, author: str) -> dict:
    """DB에서 책 조회 → 없으면 알라딘 API로 검증 후 저장.

    시스템 2 LLM 추천 결과의 book_id를 항상 확보하기 위해 사용.
    """
    from app.services.aladin import search_books as aladin_search
    from app.services.aladin_supplement import _find_existing_book, _save_new_book

    empty = {"book_id": "", "title": title, "author": author,
             "isbn": "", "cover_image_url": "", "description": "", "genre": ""}
    if not title:
        return empty

    # 1. DB에서 먼저 조회
    result = await db.execute(
        select(Book).where(Book.title.ilike(f"%{title}%")).limit(1)
    )
    book = result.scalar_one_or_none()

    # 2. DB에 없으면 알라딘 검증 후 저장
    if not book:
        try:
            aladin_results = await aladin_search(f"{title} {author}".strip(), max_results=3)
            for aladin_book in aladin_results:
                if title.strip().lower() in aladin_book.title.strip().lower():
                    from app.schemas.book import BookSearchResult
                    book = await _save_new_book(db, aladin_book)
                    if book:
                        logger.info("[ask] 알라딘 검증 후 저장: '%s'", book.title)
                        break
        except Exception:
            logger.warning("[ask] 알라딘 검색 실패: title='%s'", title)

    if not book:
        return empty

    return {
        "book_id": str(book.id),
        "title": book.title,
        "author": book.author or author,
        "isbn": book.isbn or "",
        "cover_image_url": book.cover_image_url or "",
        "description": book.description or "",
        "genre": book.genre or "",
    }


def _to_response(r: dict) -> RecommendationResponse:
    """추천 dict를 RecommendationResponse로 변환."""
    return RecommendationResponse(
        book_id=UUID(r["book_id"]),
        title=r["title"],
        author=r["author"],
        description=r.get("description", ""),
        genre=r.get("genre", ""),
        cover_image_url=r.get("cover_image_url", ""),
        score=r["score"],
        reason=r["reason"],
    )


def _build_profile_context(profile_data: dict) -> str:
    """취향 프로필 딕셔너리를 LLM 컨텍스트 문자열로 변환."""
    if not profile_data:
        return "취향 프로필 없음 (독서 기록 부족)"

    parts = []
    if profile_data.get("preference_summary"):
        parts.append(f"취향 요약: {profile_data['preference_summary']}")
    if profile_data.get("preferred_genres"):
        parts.append(f"선호 장르: {', '.join(profile_data['preferred_genres'])}")
    if profile_data.get("disliked_genres"):
        parts.append(f"비선호 장르: {', '.join(profile_data['disliked_genres'])}")
    if profile_data.get("top_rated_books"):
        books = [f"{b.get('title')} (★{b.get('rating')})" for b in profile_data["top_rated_books"][:5]]
        parts.append(f"최고 평점 도서: {', '.join(books)}")
    if profile_data.get("reading_count"):
        parts.append(f"총 독서 수: {profile_data['reading_count']}권")

    return "\n".join(parts) if parts else "취향 정보 없음"


def _build_rag_context(chunks: list[dict]) -> str:
    """RAG 검색 청크 목록을 LLM 컨텍스트 문자열로 변환."""
    if not chunks:
        return "관련 정보 없음"

    lines = ["## 추천 및 후기 참고 자료"]
    for i, chunk in enumerate(chunks[:7], 1):
        lines.append(f"{i}. {chunk['text'][:200]}")

    return "\n".join(lines)


async def _ask_llm(
    question: str,
    profile_context: str,
    rag_context: str,
    limit: int,
) -> list[dict]:
    """LLM으로 질문 기반 책 추천 생성.

    Returns:
        [{"title": ..., "author": ..., "reason_hint": ...}] 리스트
    """
    system_prompt = (
        "당신은 한국 독서 추천 전문가입니다. "
        "사용자의 취향 프로필과 추천 자료를 참고하여 "
        "사용자의 질문에 맞는 책을 추천해주세요.\n\n"
        f"## 사용자 취향 프로필\n{profile_context}\n\n"
        f"{rag_context}\n\n"
        "## 지시사항\n"
        "- 반드시 실제 출판된 책만 제시 (가공의 책 절대 금지)\n"
        "- 한국 알라딘 서점에서 구매 가능한 책\n"
        "- 비선호 장르는 포함하지 마세요\n"
        "- reason_hint는 이 책을 추천하는 이유 (1-2문장)\n"
        f"반드시 {limit}권의 책을 JSON 배열로만 반환하세요:\n"
        '[{"title": "책 제목", "author": "저자명", "reason_hint": "추천 이유"}]'
    )

    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            max_tokens=800,
            temperature=0.4,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        suggestions = json.loads(raw)

        if not isinstance(suggestions, list):
            logger.warning("[ask-llm] Invalid response format")
            return []

        logger.info("[ask-llm] Generated %d suggestions for question '%s'", len(suggestions), question)
        return suggestions[:limit * 2]

    except Exception as e:
        logger.error("[ask-llm] LLM call failed: %s", e)
        return []


# ── 관리자 라우터 ─────────────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/index-knowledge", response_model=PipelineStatusResponse)
async def index_knowledge_base(
    current_user: User = Depends(get_current_user),
):
    """rag_knowledge 인덱스: 데이터를 파싱하여 임베딩 적재 (관리자).

    /app/output 디렉토리의 파일을 읽어 rag_knowledge 인덱스에 청크 적재.
    OpenAI API 과금이 발생합니다.
    """
    from app.services.rag_pipeline.pipeline import RagPipeline

    pipeline = RagPipeline(data_dir=Path("/app/output"))
    result = await pipeline.run()

    logger.info(
        "[admin] index-knowledge: total=%d indexed=%d skipped=%d errors=%d",
        result.total, result.indexed, result.skipped, result.errors,
    )

    return PipelineStatusResponse(
        total=result.total,
        indexed=result.indexed,
        skipped=result.skipped,
        errors=result.errors,
        source_stats=result.source_stats,
    )


@admin_router.post("/index-books", response_model=IndexStatusResponse)
async def index_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """books DB → OpenSearch books 인덱스 전체 임베딩/upsert (관리자).

    OpenAI API 과금이 발생합니다.
    """
    from app.services.book_indexer import index_all_books

    result = await index_all_books(db)

    logger.info(
        "[admin] index-books: indexed=%d failed=%d total_tokens=%d",
        result["indexed"], result["failed"], result["total_tokens"],
    )

    return IndexStatusResponse(
        indexed=result["indexed"],
        failed=result["failed"],
        total_tokens=result["total_tokens"],
    )


@admin_router.post("/index-user-books", response_model=IndexStatusResponse)
async def index_user_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """user_books 평점/메모 → OpenSearch user_books 인덱스 전체 임베딩/upsert (관리자).

    메모가 있는 항목만 OpenAI API 과금이 발생합니다.
    book_embedding은 books 인덱스에서 조회 (재임베딩 없음).
    """
    from app.services.user_book_indexer import index_all_user_books

    result = await index_all_user_books(db)

    logger.info(
        "[admin] index-user-books: indexed=%d failed=%d skipped=%d total_tokens=%d",
        result["indexed"], result["failed"], result["skipped"], result["total_tokens"],
    )

    return IndexStatusResponse(
        indexed=result["indexed"],
        failed=result["failed"],
        skipped=result["skipped"],
        total_tokens=result["total_tokens"],
    )


@admin_router.post("/seed-books", response_model=SeedStatusResponse)
async def seed_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """데이터에서 책 제목을 추출하여 books DB에 시딩 (관리자).

    알라딘 API로 실존 검증 후 DB에 저장.
    """
    from app.services.data_seeder import seed_books_from_data

    result = await seed_books_from_data(db, data_dir=Path("/app/output"))

    logger.info(
        "[admin] seed-books: total=%d seeded=%d skipped=%d errors=%d",
        result.total, result.seeded, result.skipped, result.errors,
    )

    return SeedStatusResponse(
        total=result.total,
        seeded=result.seeded,
        skipped=result.skipped,
        errors=result.errors,
    )
