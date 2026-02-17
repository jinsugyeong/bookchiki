"""추천 서비스: LLM 기반 추천 방향 설계 + 알라딘 실재 도서 검증 + KNN 혼합 파이프라인."""

import json
import logging
from collections import Counter
from datetime import date, datetime, timezone
from uuid import UUID

import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.book import Book
from app.models.user_book import UserBook
from app.models.recommendation import Recommendation
from app.services.rag import embed_text, knn_search, count_indexed, index_book
from app.services.aladin import search_books as aladin_search

logger = logging.getLogger(__name__)

_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# --- 캐시 ---
# 추천 결과 캐시: user_id -> (timestamp, recommendations)
_recommendation_cache: dict[UUID, tuple[datetime, list[dict]]] = {}
CACHE_TTL_SECONDS = 3600  # 1시간

# 메모 분석 캐시: user_id -> (timestamp, analysis_result)
_memo_analysis_cache: dict[UUID, tuple[datetime, dict]] = {}
MEMO_CACHE_TTL_SECONDS = 7200  # 2시간

# --- 시딩 상수 ---
MIN_INDEX_SIZE = 50
MAX_SEED_PER_REQUEST = 30
MAX_SEED_PER_DAY = 3
SEED_SEARCH_PER_GENRE = 10

# 일일 시딩 추적: user_id -> (date, count)
_seed_tracker: dict[UUID, tuple[date, int]] = {}

# DB 컬럼 길이 제한 (Book 모델과 일치)
_MAX_TITLE = 500
_MAX_AUTHOR = 1000
_MAX_GENRE = 500
_MAX_COVER_URL = 500


def _safe_book_kwargs(item) -> dict:
    """알라딘 검색 결과를 Book 생성 kwargs로 변환 (컬럼 길이 초과 방지)."""
    return {
        "title": (item.title or "")[:_MAX_TITLE],
        "author": (item.author or "")[:_MAX_AUTHOR],
        "isbn": item.isbn,
        "description": item.description,
        "cover_image_url": (item.cover_image_url or "")[:_MAX_COVER_URL],
        "genre": (item.genre or "")[:_MAX_GENRE],
        "published_at": item.published_at,
    }


def invalidate_cache(user_id: UUID) -> None:
    """유저의 추천 캐시 및 메모 분석 캐시 무효화 (평점/메모 변경 시 호출)."""
    _recommendation_cache.pop(user_id, None)
    _memo_analysis_cache.pop(user_id, None)
    logger.info("Invalidated recommendation + memo cache for user %s", user_id)


def _check_seed_limit(user_id: UUID) -> bool:
    """오늘 시딩 가능 여부 확인. 가능하면 True 반환."""
    today = date.today()
    if user_id in _seed_tracker:
        tracked_date, count = _seed_tracker[user_id]
        if tracked_date == today:
            return count < MAX_SEED_PER_DAY
    return True


def _increment_seed_count(user_id: UUID) -> None:
    """유저의 오늘 시딩 횟수를 1 증가."""
    today = date.today()
    if user_id in _seed_tracker:
        tracked_date, count = _seed_tracker[user_id]
        if tracked_date == today:
            _seed_tracker[user_id] = (today, count + 1)
            return
    _seed_tracker[user_id] = (today, 1)


def _extract_top_genres(user_books: list[UserBook], top_n: int = 3) -> list[str]:
    """유저 서재에서 최하위 장르명 기준 상위 장르 추출."""
    genre_counter: Counter[str] = Counter()
    for ub in user_books:
        if not ub.book or not ub.book.genre:
            continue
        # "국내도서>소설/시/희곡>한국소설" → "한국소설"
        genre_parts = ub.book.genre.split(">")
        last_level = genre_parts[-1].strip()
        if last_level:
            genre_counter[last_level] += 1
    return [genre for genre, _ in genre_counter.most_common(top_n)]


# ──────────────────────────────────────────────
# 1단계: 메모 분석 (캐싱 포함)
# ──────────────────────────────────────────────

async def _analyze_user_memos(user_books: list[UserBook]) -> dict:
    """GPT-4o-mini로 유저 메모를 분석해서 선호/비선호 장르 및 취향 요약 추출."""
    memos = []
    for ub in user_books:
        if ub.memo and ub.memo.strip():
            book_title = ub.book.title if ub.book else "?"
            memos.append(f"[{book_title}] {ub.memo.strip()}")

    if not memos:
        return {"preferred_genres": [], "disliked_genres": [], "preferences": ""}

    prompt = (
        "유저의 독서 메모들을 분석해서 JSON으로 반환해주세요.\n"
        "반드시 아래 형식의 JSON만 반환하세요 (다른 텍스트 없이):\n"
        '{"preferred_genres": ["장르1", "장르2"], "disliked_genres": ["장르1"], '
        '"preferences": "유저 취향 요약 한 문장"}\n\n'
        "메모들:\n" + "\n".join(memos[:20])
    )

    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        logger.info("[memo-analysis] result=%s", result)
        return result
    except Exception:
        logger.exception("Failed to analyze user memos")
        return {"preferred_genres": [], "disliked_genres": [], "preferences": ""}


async def get_memo_analysis(user_id: UUID, user_books: list[UserBook]) -> dict:
    """메모 분석 결과를 캐시에서 조회하거나 새로 생성."""
    now = datetime.now(timezone.utc)
    if user_id in _memo_analysis_cache:
        cached_at, cached = _memo_analysis_cache[user_id]
        elapsed = (now - cached_at).total_seconds()
        if elapsed < MEMO_CACHE_TTL_SECONDS:
            logger.info("[memo-cache] HIT for user %s (age=%.0fs)", user_id, elapsed)
            return cached

    logger.info("[memo-cache] MISS for user %s, analyzing...", user_id)
    result = await _analyze_user_memos(user_books)
    _memo_analysis_cache[user_id] = (now, result)
    return result


# ──────────────────────────────────────────────
# 2단계: 유저 요약 헬퍼
# ──────────────────────────────────────────────

def _build_user_summary(user_books: list[UserBook]) -> str:
    """유저의 평점 높은 도서 목록을 텍스트 요약으로 생성."""
    rated_books = [ub for ub in user_books if ub.rating is not None]
    summary_parts = []
    for ub in sorted(rated_books, key=lambda x: x.rating or 0, reverse=True)[:10]:
        if ub.book:
            summary_parts.append(f"- {ub.book.title} ({ub.book.author}) ★{ub.rating}")
    return "\n".join(summary_parts) if summary_parts else "독서 기록 없음"


# ──────────────────────────────────────────────
# 3단계: LLM 추천 방향 생성 (NEW)
# ──────────────────────────────────────────────

async def generate_recommendation_directions(
    user_summary: str,
    memo_analysis: dict,
    top_genres: list[str],
    num_directions: int = 5,
) -> list[dict]:
    """LLM이 사용자 취향 기반으로 추천 검색 방향을 설계.

    반환: [{"search_keyword", "genre", "mood", "reason_hint"}, ...]
    - 선호 장르 기반 3개 + 다양성 확보용 2개 방향 생성
    - 알라딘에서 검색 가능한 구체적 키워드 포함
    """
    preferences = memo_analysis.get("preferences", "")
    preferred = memo_analysis.get("preferred_genres", [])
    disliked = memo_analysis.get("disliked_genres", [])

    prompt = (
        "당신은 독서 추천 전문가입니다. 사용자의 독서 기록과 취향을 분석하여 "
        "추천 도서를 찾기 위한 검색 방향을 설계해주세요.\n\n"
        f"## 사용자 독서 기록\n{user_summary}\n\n"
        f"## 취향 분석\n{preferences if preferences else '분석 없음'}\n"
        f"## 선호 장르: {', '.join(preferred) if preferred else ', '.join(top_genres)}\n"
        f"## 비선호 장르: {', '.join(disliked) if disliked else '없음'}\n\n"
        f"## 지시사항\n"
        f"정확히 {num_directions}개의 추천 방향을 JSON 배열로 반환하세요.\n"
        f"- 선호 장르 기반 {max(num_directions - 2, 1)}개\n"
        f"- 다양성 확보용 (선호 장르 외) {min(2, num_directions - 1)}개\n"
        "- 비선호 장르는 절대 포함하지 마세요\n"
        "- search_keyword는 알라딘에서 검색 가능한 구체적인 한국어 키워드 (2~4단어)\n"
        "- mood는 책의 분위기를 한 단어로 (예: 따뜻한, 긴장감, 철학적)\n"
        "- reason_hint는 이 방향으로 추천하는 이유 힌트 (1문장)\n\n"
        "반드시 아래 형식의 JSON 배열만 반환하세요 (다른 텍스트 없이):\n"
        '[{"search_keyword": "키워드", "genre": "장르", "mood": "분위기", '
        '"reason_hint": "추천 이유 힌트"}]'
    )

    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.8,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        directions = json.loads(raw)

        if not isinstance(directions, list) or len(directions) == 0:
            raise ValueError("Empty or invalid directions list")

        logger.info("[directions] LLM generated %d directions: %s",
                    len(directions), [d.get("search_keyword") for d in directions])
        return directions[:num_directions]

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("[directions] LLM returned invalid response: %s, using fallback", e)
        return _fallback_directions(top_genres, preferred, disliked)
    except Exception:
        logger.exception("[directions] LLM direction generation failed, using fallback")
        return _fallback_directions(top_genres, preferred, disliked)


def _fallback_directions(
    top_genres: list[str],
    preferred: list[str],
    disliked: list[str],
) -> list[dict]:
    """LLM 방향 생성 실패 시 장르 기반 폴백 방향 생성."""
    disliked_set = {g.lower() for g in disliked}
    directions = []

    candidates = top_genres + [g for g in preferred if g not in top_genres]
    for genre in candidates:
        if genre.lower() not in disliked_set and len(directions) < 5:
            directions.append({
                "search_keyword": f"{genre} 추천 도서",
                "genre": genre,
                "mood": "",
                "reason_hint": f"선호 장르인 {genre} 기반 추천",
            })

    if not directions:
        directions.append({
            "search_keyword": "베스트셀러",
            "genre": "",
            "mood": "",
            "reason_hint": "인기 도서 기반 추천",
        })

    return directions


# ──────────────────────────────────────────────
# 4단계: 알라딘 기반 도서 후보 수집 (NEW)
# ──────────────────────────────────────────────

async def _fetch_candidates_from_aladin(
    db: AsyncSession,
    directions: list[dict],
    exclude_book_ids: list[str],
    max_per_direction: int = 5,
) -> list[dict]:
    """각 추천 방향의 search_keyword로 알라딘 검색 후 후보 수집.

    중복/읽은 책 제거 -> DB flush (commit은 호출자가 담당) + 인덱싱
    -> mood, reason_hint 첨부하여 반환.
    """
    # 기존 도서 중복 체크용 맵 (N+1 쿼리 방지)
    all_books_result = await db.execute(select(Book))
    all_books = all_books_result.scalars().all()
    existing_isbns = {b.isbn for b in all_books if b.isbn}
    existing_title_author = {
        (b.title.strip().lower(), (b.author or "").strip().lower())
        for b in all_books
    }
    # O(1) 룩업용 딕셔너리
    isbn_to_book: dict[str, Book] = {b.isbn: b for b in all_books if b.isbn}
    title_author_to_book: dict[tuple[str, str], Book] = {
        (b.title.strip().lower(), (b.author or "").strip().lower()): b
        for b in all_books
    }

    # book_id 기준으로 이미 서재에 있는 책 제외 + 이번 수집에서 중복 방지
    exclude_set = set(exclude_book_ids)
    collected_book_ids: set[str] = set()
    candidates: list[dict] = []

    def _make_candidate(book: Book, direction: dict) -> dict:
        """Book 객체에서 후보 dict 생성."""
        return {
            "book_id": str(book.id),
            "title": book.title,
            "author": book.author or "",
            "description": book.description or "",
            "genre": book.genre or "",
            "cover_image_url": book.cover_image_url or "",
            "score": 0.0,
            "mood": direction.get("mood", ""),
            "reason_hint": direction.get("reason_hint", ""),
            "source": "aladin",
        }

    for direction in directions:
        keyword = direction.get("search_keyword", "")
        if not keyword:
            continue

        logger.info("[aladin-fetch] Searching: '%s'", keyword)
        try:
            results = await aladin_search(keyword, max_results=max_per_direction)
        except Exception:
            logger.warning("[aladin-fetch] Search failed for '%s'", keyword)
            continue

        for item in results:
            if not item.description:
                continue

            # ISBN 중복 확인 → 메모리 딕셔너리 룩업
            if item.isbn and item.isbn in existing_isbns:
                existing_book = isbn_to_book.get(item.isbn)
                if existing_book and str(existing_book.id) not in exclude_set \
                        and str(existing_book.id) not in collected_book_ids:
                    collected_book_ids.add(str(existing_book.id))
                    candidates.append(_make_candidate(existing_book, direction))
                continue

            # title+author 중복 확인 → 메모리 딕셔너리 룩업
            title_key = (item.title.strip().lower(), item.author.strip().lower())
            if title_key in existing_title_author:
                existing_book = title_author_to_book.get(title_key)
                if existing_book and str(existing_book.id) not in exclude_set \
                        and str(existing_book.id) not in collected_book_ids:
                    collected_book_ids.add(str(existing_book.id))
                    candidates.append(_make_candidate(existing_book, direction))
                continue

            # 새 도서: DB flush + 인덱싱 (commit은 호출자 담당)
            book = Book(**_safe_book_kwargs(item))
            db.add(book)
            await db.flush()

            try:
                await index_book(book)
                if item.isbn:
                    existing_isbns.add(item.isbn)
                    isbn_to_book[item.isbn] = book
                existing_title_author.add(title_key)
                title_author_to_book[title_key] = book

                collected_book_ids.add(str(book.id))
                candidates.append(_make_candidate(book, direction))
                logger.info("[aladin-fetch] New book indexed: '%s'", book.title)
            except Exception:
                logger.warning("[aladin-fetch] Failed to index '%s'", book.title)

    logger.info("[aladin-fetch] Collected %d candidates from %d directions",
                len(candidates), len(directions))
    return candidates


# ──────────────────────────────────────────────
# 5단계: 후보 혼합 함수 (NEW)
# ──────────────────────────────────────────────

def _merge_candidates(
    aladin_candidates: list[dict],
    knn_candidates: list[dict],
    limit: int = 10,
    aladin_ratio: float = 0.6,
) -> list[dict]:
    """알라딘 후보와 KNN 후보를 비율에 따라 혼합.

    aladin_ratio=0.6이면 알라딘 60%, KNN 40% 비율로 혼합.
    book_id 기준 중복 제거.
    """
    aladin_count = min(int(limit * aladin_ratio), len(aladin_candidates))
    knn_count = limit - aladin_count

    merged: list[dict] = []
    seen_ids: set[str] = set()

    # 알라딘 후보 먼저
    for candidate in aladin_candidates:
        if len(merged) >= aladin_count:
            break
        bid = candidate["book_id"]
        if bid not in seen_ids:
            seen_ids.add(bid)
            merged.append(candidate)

    # KNN 후보
    for candidate in knn_candidates:
        if len(merged) >= limit:
            break
        bid = candidate["book_id"]
        if bid not in seen_ids:
            seen_ids.add(bid)
            merged.append(candidate)

    # 아직 limit 미달이면 남은 알라딘 후보로 채움
    for candidate in aladin_candidates:
        if len(merged) >= limit:
            break
        bid = candidate["book_id"]
        if bid not in seen_ids:
            seen_ids.add(bid)
            merged.append(candidate)

    logger.info("[merge] Merged %d candidates (aladin=%d, knn=%d)",
                len(merged),
                sum(1 for c in merged if c.get("source") == "aladin"),
                sum(1 for c in merged if c.get("source") != "aladin"))
    return merged


# ──────────────────────────────────────────────
# 기존 유지: 시딩, 선호도 벡터
# ──────────────────────────────────────────────

async def _seed_books_from_aladin(
    db: AsyncSession,
    user_id: UUID,
    user_books: list[UserBook],
    memo_analysis: dict | None = None,
) -> int:
    """인덱스 크기가 부족할 때 알라딘에서 책을 자동 시딩. 새로 시딩된 권수 반환."""
    indexed_count = count_indexed()
    if indexed_count >= MIN_INDEX_SIZE:
        logger.info("[seed] Index has %d docs (>= %d), skipping", indexed_count, MIN_INDEX_SIZE)
        return 0

    if not _check_seed_limit(user_id):
        logger.info("[seed] Daily seed limit reached for user %s", user_id)
        return 0

    logger.info("[seed] Index has %d docs (< %d), starting auto-seed", indexed_count, MIN_INDEX_SIZE)

    top_genres = _extract_top_genres(user_books)
    logger.info("[seed] Top genres from library: %s", top_genres)

    if memo_analysis is None:
        memo_analysis = await _analyze_user_memos(user_books)
    preferred = memo_analysis.get("preferred_genres", [])
    disliked = set(g.lower() for g in memo_analysis.get("disliked_genres", []))

    search_keywords = []
    for g in top_genres:
        if g.lower() not in disliked:
            search_keywords.append(g)
    for g in preferred:
        if g.lower() not in disliked and g not in search_keywords:
            search_keywords.append(g)

    if not search_keywords:
        search_keywords = ["베스트셀러"]

    logger.info("[seed] Search keywords: %s (disliked: %s)", search_keywords, disliked)

    all_books_result = await db.execute(select(Book))
    all_books = all_books_result.scalars().all()
    existing_isbns = {b.isbn for b in all_books if b.isbn}
    existing_title_author = {(b.title.strip().lower(), (b.author or "").strip().lower()) for b in all_books}

    seeded = 0
    for keyword in search_keywords:
        if seeded >= MAX_SEED_PER_REQUEST:
            break

        try:
            results = await aladin_search(keyword, max_results=SEED_SEARCH_PER_GENRE)
        except Exception:
            logger.warning("[seed] Aladin search failed for '%s'", keyword)
            continue

        for item in results:
            if seeded >= MAX_SEED_PER_REQUEST:
                break
            if item.isbn and item.isbn in existing_isbns:
                continue
            title_key = (item.title.strip().lower(), item.author.strip().lower())
            if title_key in existing_title_author:
                continue
            if not item.description:
                continue

            book = Book(**_safe_book_kwargs(item))
            db.add(book)
            await db.flush()

            try:
                await index_book(book)
                seeded += 1
                if item.isbn:
                    existing_isbns.add(item.isbn)
                existing_title_author.add(title_key)
                logger.info("[seed] Indexed '%s' by %s", item.title, item.author)
            except Exception:
                logger.warning("[seed] Failed to index '%s'", item.title)

    # commit은 호출자(get_recommendations)가 담당
    if seeded > 0:
        _increment_seed_count(user_id)

    logger.info("[seed] Seeded %d books from Aladin", seeded)
    return seeded


async def compute_user_preference_vector(
    db: AsyncSession, user_id: UUID
) -> list[float] | None:
    """유저의 평점 기반 가중 선호도 벡터 계산.

    높은 평점일수록 벡터에 더 큰 가중치 부여.
    가중치 공식: rating / 5.0 (5점 = 1.0, 1점 = 0.2)
    """
    result = await db.execute(
        select(UserBook)
        .options(joinedload(UserBook.book))
        .where(
            UserBook.user_id == user_id,
            UserBook.rating.isnot(None),
        )
    )
    rated_books = result.unique().scalars().all()

    if not rated_books:
        return None

    embeddings = []
    weights = []

    for ub in rated_books:
        if not ub.book or not ub.book.description:
            continue

        parts = [ub.book.title]
        if ub.book.author:
            parts.append(f"저자: {ub.book.author}")
        if ub.book.genre:
            parts.append(f"장르: {ub.book.genre}")
        if ub.book.description:
            parts.append(ub.book.description)
        text = " | ".join(parts)

        try:
            emb, _ = await embed_text(text)
            embeddings.append(emb)
            weights.append(ub.rating / 5.0)
        except Exception:
            logger.warning("Failed to embed book %s for preference vector", ub.book_id)

    if not embeddings:
        return None

    arr = np.array(embeddings)
    w = np.array(weights).reshape(-1, 1)
    weighted = (arr * w).sum(axis=0) / w.sum()

    norm = np.linalg.norm(weighted)
    if norm > 0:
        weighted = weighted / norm

    return weighted.tolist()


# ──────────────────────────────────────────────
# 6단계: generate_recommendation_reason 수정
# ──────────────────────────────────────────────

async def generate_recommendation_reason(
    user_books_summary: str,
    recommended_book: dict,
    user_preferences: str = "",
    reason_hint: str = "",
) -> str:
    """GPT-4o-mini를 사용해 한국어 추천 이유 생성.

    reason_hint가 있으면 LLM이 해당 방향으로 추천 이유를 작성.
    """
    pref_section = ""
    if user_preferences:
        pref_section = f"\n사용자 취향 분석: {user_preferences}\n"

    hint_section = ""
    if reason_hint:
        hint_section = f"\n추천 방향 힌트: {reason_hint}\n"

    prompt = (
        "당신은 책 추천 전문가입니다. 사용자의 독서 기록을 바탕으로 "
        "왜 이 책을 추천하는지 간결하고 매력적인 한국어 추천 이유를 작성해주세요.\n\n"
        f"사용자 독서 기록 요약:\n{user_books_summary}\n"
        f"{pref_section}"
        f"{hint_section}\n"
        f"추천 도서: {recommended_book['title']} (저자: {recommended_book['author']})\n"
        f"설명: {recommended_book.get('description', '정보 없음')}\n\n"
        "추천 이유를 2-3문장으로 작성해주세요."
    )

    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("Failed to generate recommendation reason")
        return "독서 취향 분석을 기반으로 추천된 도서입니다."


# ──────────────────────────────────────────────
# 7단계: get_recommendations 리팩터링
# ──────────────────────────────────────────────

async def get_recommendations(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 10,
    force_refresh: bool = False,
) -> list[dict]:
    """LLM 기반 추천 방향 설계 + 알라딘 실재 도서 검증 + KNN 혼합 파이프라인.

    1. 캐시 확인
    2. 유저 서재 로드
    3. 취향 분석 (캐싱)
    4. 유저 요약 생성
    5. 인덱스 부족 시 알라딘 자동 시딩
    6. LLM 추천 방향 생성
    7. 알라딘 후보 수집
    8. KNN 후보 수집
    9. 후보 혼합
    10. 추천 이유 생성
    11. DB 저장 + 캐시 -> 반환
    """
    # 1. 캐시 확인
    if not force_refresh and user_id in _recommendation_cache:
        cached_at, cached = _recommendation_cache[user_id]
        elapsed = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if elapsed < CACHE_TTL_SECONDS:
            logger.info("[recommend] Cache HIT for user %s", user_id)
            return cached[:limit]

    logger.info("[recommend] === 추천 파이프라인 시작 (user=%s, limit=%d) ===", user_id, limit)

    # 2. 유저 서재 로드
    user_books_result = await db.execute(
        select(UserBook)
        .options(joinedload(UserBook.book))
        .where(UserBook.user_id == user_id)
    )
    user_books = user_books_result.unique().scalars().all()
    user_book_ids = [str(ub.book_id) for ub in user_books]

    # 서재가 비어있으면 베스트셀러 기반 기본 추천
    if not user_books:
        logger.info("[recommend] Empty library, returning bestseller fallback")
        return await _bestseller_fallback(db, user_id, limit)

    # 3. 취향 분석 (캐싱)
    memo_analysis = await get_memo_analysis(user_id, user_books)
    user_preferences = memo_analysis.get("preferences", "")

    # 4. 유저 요약 생성
    user_summary = _build_user_summary(user_books)

    # 5. 인덱스 부족 시 알라딘 자동 시딩
    seeded = await _seed_books_from_aladin(db, user_id, user_books, memo_analysis)
    if seeded > 0:
        logger.info("[recommend] Seeded %d books before recommendation", seeded)

    # 6. LLM 추천 방향 생성
    top_genres = _extract_top_genres(user_books)
    directions = await generate_recommendation_directions(
        user_summary, memo_analysis, top_genres, num_directions=5
    )
    logger.info("[recommend] Generated %d directions", len(directions))

    # 7. 알라딘 후보 수집
    aladin_candidates = await _fetch_candidates_from_aladin(
        db, directions, exclude_book_ids=user_book_ids, max_per_direction=5
    )

    # 8. KNN 후보 수집 (평점이 있는 경우에만)
    knn_candidates = []
    pref_vector = await compute_user_preference_vector(db, user_id)
    if pref_vector is not None:
        try:
            knn_results = await knn_search(
                vector=pref_vector,
                k=limit + len(user_book_ids),
                exclude_book_ids=user_book_ids if user_book_ids else None,
            )
        except Exception:
            logger.warning("[recommend] KNN search failed (index may be empty), skipping")
            knn_results = []
        # KNN 결과에 cover_image_url을 DB에서 일괄 조회
        knn_trimmed = knn_results[:limit]
        if knn_trimmed:
            knn_book_ids = [UUID(item["book_id"]) for item in knn_trimmed]
            cover_result = await db.execute(
                select(Book.id, Book.cover_image_url).where(Book.id.in_(knn_book_ids))
            )
            cover_map = {str(row.id): row.cover_image_url or "" for row in cover_result}
        else:
            cover_map = {}

        for item in knn_trimmed:
            item["source"] = "knn"
            item["mood"] = ""
            item["reason_hint"] = ""
            item["cover_image_url"] = cover_map.get(item["book_id"], "")
        knn_candidates = knn_trimmed
        logger.info("[recommend] KNN returned %d candidates", len(knn_candidates))
    else:
        logger.info("[recommend] No preference vector (no ratings), skipping KNN")

    # 9. 후보 혼합
    if aladin_candidates and knn_candidates:
        merged = _merge_candidates(aladin_candidates, knn_candidates, limit=limit)
    elif aladin_candidates:
        merged = aladin_candidates[:limit]
    elif knn_candidates:
        merged = knn_candidates[:limit]
    else:
        logger.info("[recommend] No candidates found")
        return []

    if not merged:
        return []

    # 10. 추천 이유 생성 + 11. DB 저장
    recommendations = []

    await db.execute(
        delete(Recommendation).where(Recommendation.user_id == user_id)
    )

    for item in merged:
        reason = await generate_recommendation_reason(
            user_summary, item, user_preferences,
            reason_hint=item.get("reason_hint", ""),
        )

        rec = Recommendation(
            user_id=user_id,
            book_id=UUID(item["book_id"]),
            score=item.get("score", 0.0),
            reason=reason,
        )
        db.add(rec)

        recommendations.append({
            "book_id": item["book_id"],
            "title": item["title"],
            "author": item["author"],
            "description": item.get("description", ""),
            "genre": item.get("genre", ""),
            "cover_image_url": item.get("cover_image_url", ""),
            "mood": item.get("mood", ""),
            "score": item.get("score", 0.0),
            "reason": reason,
        })

    await db.commit()

    # 캐시 업데이트
    _recommendation_cache[user_id] = (datetime.now(timezone.utc), recommendations)

    logger.info("[recommend] === 파이프라인 완료: %d건 추천 생성 ===", len(recommendations))
    return recommendations


async def _bestseller_fallback(
    db: AsyncSession,
    user_id: UUID,
    limit: int,
) -> list[dict]:
    """서재가 비어있는 유저를 위한 베스트셀러 기반 기본 추천."""
    logger.info("[fallback] Fetching bestseller recommendations")

    directions = [{
        "search_keyword": "베스트셀러",
        "genre": "",
        "mood": "인기",
        "reason_hint": "많은 독자들에게 사랑받는 인기 도서",
    }, {
        "search_keyword": "올해의 책",
        "genre": "",
        "mood": "화제",
        "reason_hint": "올해 화제가 된 주목할 만한 도서",
    }]

    candidates = await _fetch_candidates_from_aladin(
        db, directions, exclude_book_ids=[], max_per_direction=limit
    )

    recommendations = []
    await db.execute(
        delete(Recommendation).where(Recommendation.user_id == user_id)
    )

    for item in candidates[:limit]:
        reason = item.get("reason_hint", "인기 도서입니다.")

        rec = Recommendation(
            user_id=user_id,
            book_id=UUID(item["book_id"]),
            score=0.0,
            reason=reason,
        )
        db.add(rec)

        recommendations.append({
            "book_id": item["book_id"],
            "title": item["title"],
            "author": item["author"],
            "description": item.get("description", ""),
            "genre": item.get("genre", ""),
            "cover_image_url": item.get("cover_image_url", ""),
            "mood": item.get("mood", ""),
            "score": 0.0,
            "reason": reason,
        })

    if recommendations:
        await db.commit()
        _recommendation_cache[user_id] = (datetime.now(timezone.utc), recommendations)

    logger.info("[fallback] Generated %d bestseller recommendations", len(recommendations))
    return recommendations
