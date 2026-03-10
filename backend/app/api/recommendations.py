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
from app.models.ask_history import AskHistory
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
    AskHistoryResponse,
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


async def _fetch_books_via_web_search(query: str) -> list[dict]:
    """httpx를 사용하여 실시간 도서 정보를 검색하고 후보 목록을 생성."""
    import httpx
    from app.core.config import settings

    tavily_api_key = getattr(settings, "TAVILY_API_KEY", None)
    if not tavily_api_key:
        logger.warning("[WebSearch] TAVILY_API_KEY가 없습니다.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": tavily_api_key,
        "query": f"실제 출판된 한국 도서 추천: {query}",
        "search_depth": "advanced",
        "max_results": 8
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error("[WebSearch] Tavily API 오류: %s", resp.text)
                return []
            data = resp.json()
                
        search_context = "\n".join([r.get("content", "") for r in data.get("results", [])])
        
        # 검색 결과에서 제목/저자 추출 (Strict Extraction)
        extraction_prompt = (
            "다음 검색 결과에서 언급된 실제 도서들의 [제목]과 [저자]를 추출하세요.\n"
            "한국어로 출판된 실존 도서여야 합니다.\n"
            "JSON 형식: " + '{"books": [{"title": "제목", "author": "저자"}]}' + 
            f"\n\n검색 결과:\n{search_context}"
        )
        
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": extraction_prompt}],
            response_format={"type": "json_object"}
        )
        extracted = json.loads(response.choices[0].message.content)
        return extracted.get("books", [])
    except Exception as e:
        logger.error("[WebSearch] 실패: %s", e)
        return []

@router.post("/ask", response_model=AskResponse)
async def ask_recommendations(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """최종 엄격 검증 파이프라인: Web Search -> LLM Selection -> Strict Aladin Validation."""
    # 1. 컨텍스트 수집
    profile = await get_or_create_profile(db, current_user.id)
    profile_context = _build_profile_context(profile.profile_data or {})
    rag_chunks = await search_knowledge(request.question, k=10)
    
    # 2. 웹 검색으로 실존 후보군 확보 (항상 실행하여 최신성/실존성 보장)
    logger.info("[ask] Tavily Web Search로 실존 후보 확보 중...")
    candidate_pool = await _fetch_books_via_web_search(request.question)
    
    # 3. LLM에게 후보군 중 10권 선택 요청 (검증 탈락 대비 여유분 확보)
    pool_str = "\n".join([f"- {c['title']} ({c['author']})" for c in candidate_pool]) if candidate_pool else "지식 기반"
    
    suggestions_raw = await _ask_llm_for_selection(
        question=request.question,
        profile_context=profile_context,
        rag_context=_build_rag_context(rag_chunks),
        pool_str=pool_str,
        limit=10 # 3권을 꽉 채우기 위해 후보군 대폭 확대
    )

    logger.info("[ask] LLM 후보 수: %d / 요청: %d", len(suggestions_raw), 10)

    if not suggestions_raw:
        return AskResponse(results=[], total=0, question=request.question)

    # 4. STRICT 알라딘 검증 (실존하는 책만 결과에 추가)
    from app.models.user_book import UserBook
    library_stmt = select(Book.title).join(UserBook, Book.id == UserBook.book_id).where(UserBook.user_id == current_user.id)
    library_res = await db.execute(library_stmt)
    library_titles = {"".join(r[0].split()).lower() for r in library_res.all()}

    results = []
    seen_titles = set()

    for item in suggestions_raw:
        if len(results) >= request.limit: # 3권 채우면 종료
            break
            
        title = item.get("title", "").strip()
        author = item.get("author", "").strip()
        norm_title = "".join(title.split()).lower()
        
        if not title or norm_title in seen_titles or norm_title in library_titles:
            continue

        # [CRITICAL] 알라딘 API 실존 검증
        # _find_or_save_book 내부에서 알라딘 검색 실패 시 book_id를 반환하지 않도록 설계됨
        book_info = await _find_or_save_book_strict(db, title, author)
        bid = book_info.get("book_id", "")

        if not bid:
            logger.warning("[ask] 실존하지 않는 도서 제외: '%s'", title)
            continue

        results.append(AskResultItem(
            title=book_info["title"],
            author=book_info["author"],
            reason=item.get("reason_hint", ""),
            book_id=bid,
            isbn=book_info["isbn"],
            cover_image_url=book_info["cover_image_url"],
            genre=book_info["genre"],
            description=book_info["description"],
        ))
        seen_titles.add(norm_title)

    # 5. 이력 저장
    history = AskHistory(user_id=current_user.id, question=request.question, results=[r.model_dump() for r in results])
    db.add(history)
    await db.commit()

    return AskResponse(results=results, total=len(results), question=request.question)

async def _ask_llm_for_selection(
    question: str,
    profile_context: str,
    rag_context: str,
    pool_str: str,
    limit: int,
) -> list[dict]:
    """LLM이 후보군에서 검증할 도서를 선별."""
    system_prompt = (
        "당신은 한국 도서 추천 전문가입니다.\n"
        "사용자의 질문에서 핵심 주제(예: '아버지', '성장', '이민')를 파악하고, "
        "그 주제가 책의 중심 테마인 도서만 추천하세요.\n"
        "주제와 관련이 없는 유명 도서를 억지로 끼워넣지 마세요.\n\n"
        "아래 [후보 도서 목록]을 우선 활용하되, 목록이 부족하거나 주제에 맞지 않으면 "
        "실존하는 다른 한국 도서로 채워서 반드시 "
        f"{limit}권을 채워야 합니다.\n"
        "절대로 가공의 책을 만들어내면 안 됩니다. "
        "알라딘 서점에서 실제로 검색되는 책만 포함하세요.\n\n"
        f"## [사용자 취향]\n{profile_context}\n\n"
        f"## [참고 자료]\n{rag_context}\n\n"
        f"## [후보 도서 목록 (우선 활용)]\n{pool_str}\n\n"
        "reason_hint는 '이 책의 [핵심 테마]가 사용자 질문의 [키워드]와 "
        "어떻게 연결되는지' 구체적으로 1-2문장으로 작성하세요.\n\n"
        f"반드시 {limit}권을 JSON 배열로만 응답하세요. "
        '형식: [{"title": "제목", "author": "저자", "reason_hint": "이유"}]'
    )
    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw: raw = raw.split("```json")[-1].split("```")[0].strip()
        return json.loads(raw)
    except: return []

async def _find_or_save_book_strict(db: AsyncSession, title: str, author: str) -> dict:
    """[Strict] 알라딘 API 검색 성공 시에만 데이터를 반환."""
    from app.services.aladin import search_books as aladin_search
    from app.services.aladin_supplement import _save_new_book

    # 1. DB 조회
    res = await db.execute(select(Book).where(Book.title.ilike(f"%{title}%")).limit(1))
    book = res.scalar_one_or_none()
    
    if not book:
        # 2. 알라딘 엄격 검색 (제목 + 저자)
        try:
            search_res = await aladin_search(f"{title} {author}", max_results=3)
            for b in search_res:
                # 유연한 제목 매칭 (양방향 확인)
                norm_q = "".join(title.split()).lower()
                norm_b = "".join(b.title.split()).lower()
                if norm_q in norm_b or norm_b in norm_q:
                    book = await _save_new_book(db, b)
                    break
        except: pass

    if not book: return {} # 검증 실패

    return {
        "book_id": str(book.id),
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "cover_image_url": book.cover_image_url,
        "genre": book.genre,
        "description": book.description,
    }


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

    # 결과 기본값 (검증 실패 시에도 최소한의 정보는 반환)
    result_data = {"book_id": "", "title": title, "author": author,
                   "isbn": "", "cover_image_url": "", "description": "", "genre": ""}
    if not title:
        return result_data

    # 제목 정규화 (공백 제거, 소문자화)
    def normalize(t):
        return "".join(t.split()).lower()

    norm_title = normalize(title)

    # 1. DB에서 먼저 조회 (제목 + 저자 조합)
    query = select(Book).where(Book.title.ilike(f"%{title}%"))
    if author and len(author) > 1:
        query = query.where(Book.author.ilike(f"%{author}%"))
    
    db_result = await db.execute(query.limit(1))
    book = db_result.scalar_one_or_none()

    # 1.1 제목으로만 다시 시도
    if not book:
        db_result = await db.execute(
            select(Book).where(Book.title.ilike(f"%{title}%")).limit(1)
        )
        book = db_result.scalar_one_or_none()

    # 2. DB에 없으면 알라딘 검증 후 저장
    if not book:
        # 시도 1: 제목 + 저자
        search_queries = [f"{title} {author}", title]
        for q in search_queries:
            try:
                aladin_results = await aladin_search(q.strip(), max_results=5)
                for aladin_book in aladin_results:
                    # 유연한 제목 매칭 (포함 관계 확인)
                    if norm_title in normalize(aladin_book.title) or normalize(aladin_book.title) in norm_title:
                        from app.schemas.book import BookSearchResult
                        book = await _save_new_book(db, aladin_book)
                        if book:
                            logger.info("[ask] 알라딘 검증 성공('%s'): '%s'", q, book.title)
                            break
                if book: break
            except Exception:
                continue

    if book:
        return {
            "book_id": str(book.id),
            "title": book.title,
            "author": book.author or author,
            "isbn": book.isbn or "",
            "cover_image_url": book.cover_image_url or "",
            "description": book.description or "",
            "genre": book.genre or "",
        }

    # 검증 실패 시 원본 LLM 제안 데이터 반환 (UI에서 표시 가능하도록)
    return result_data


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


@admin_router.get("/ask-history", response_model=list[AskHistoryResponse])
async def get_ask_history(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """모든 사용자의 질문 기반 추천 이력 조회 (관리자)."""
    # TODO: 관리자 권한 체크 로직 (예: current_user.is_admin)
    result = await db.execute(
        select(AskHistory).order_by(AskHistory.created_at.desc()).limit(limit)
    )
    histories = result.scalars().all()
    return histories
