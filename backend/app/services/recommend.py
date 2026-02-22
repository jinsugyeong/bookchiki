"""추천 서비스: LLM 책 후보 생성 → 알라딘 실존 검증 → KNN 재랭킹 파이프라인."""

import asyncio
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
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
from app.services.rag import embed_text
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

# DB 컬럼 길이 제한 (Book 모델과 일치)
_MAX_TITLE = 500
_MAX_AUTHOR = 1000
_MAX_GENRE = 500
_MAX_COVER_URL = 500

# 알라딘 검증 설정
_FUZZY_TITLE_WEIGHT = 0.7
_FUZZY_AUTHOR_WEIGHT = 0.3
_FUZZY_THRESHOLD = 0.75
_MAX_ALADIN_RESULTS_PER_SUGGESTION = 5


def invalidate_cache(user_id: UUID) -> None:
    """유저의 추천 캐시 및 메모 분석 캐시 무효화 (평점/메모 변경 시 호출)."""
    _recommendation_cache.pop(user_id, None)
    _memo_analysis_cache.pop(user_id, None)
    logger.info("Invalidated recommendation + memo cache for user %s", user_id)


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
# 3단계: LLM 책 후보 생성 (NEW)
# ──────────────────────────────────────────────

async def generate_book_suggestions(
    user_summary: str,
    memo_analysis: dict,
    top_genres: list[str],
    num_suggestions: int = 25,
) -> list[dict]:
    """LLM이 사용자 취향 기반으로 구체적인 책 제목+저자를 직접 생성.

    반환: [{"title": "...", "author": "...", "reason_hint": "..."}, ...]
    - 반드시 실제 출판된 책만 제시 (할루시네이션 방지)
    - 알라딘 검증 통과율을 높이기 위해 정확한 제목+저자 필요
    - temperature=0.3으로 낮게 유지 (창의적 추측 방지)
    """
    preferences = memo_analysis.get("preferences", "")
    preferred = memo_analysis.get("preferred_genres", [])
    disliked = memo_analysis.get("disliked_genres", [])

    genre_hint = ", ".join(preferred if preferred else top_genres) or "다양한 장르"

    prompt = (
        "당신은 한국 독서 추천 전문가입니다. 사용자의 독서 취향을 분석하여 "
        "실제로 존재하는 책을 추천해주세요.\n\n"
        f"## 사용자 독서 기록\n{user_summary}\n\n"
        f"## 취향 분석\n{preferences if preferences else '분석 없음'}\n"
        f"## 선호 장르: {genre_hint}\n"
        f"## 비선호 장르: {', '.join(disliked) if disliked else '없음'}\n\n"
        "## 중요 지시사항\n"
        f"정확히 {num_suggestions}권의 도서를 JSON 배열로 반환하세요.\n"
        "- **반드시 실제 출판된 책만 제시** (가공의 작가/책 절대 금지)\n"
        "- 한국 알라딘 서점에서 구매 가능한 책 (국내서 또는 번역서)\n"
        "- 저자명은 한국어 또는 원어 그대로 정확하게 기재\n"
        "- title은 실제 출판 제목과 동일하게 (부제 제외)\n"
        "- 비선호 장르는 절대 포함하지 마세요\n"
        "- reason_hint는 이 책을 추천하는 이유 힌트 (1문장)\n\n"
        "반드시 아래 형식의 JSON 배열만 반환하세요 (다른 텍스트 없이):\n"
        '[{"title": "책 제목", "author": "저자명", "reason_hint": "추천 이유 힌트"}]'
    )

    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        suggestions = json.loads(raw)

        if not isinstance(suggestions, list) or len(suggestions) == 0:
            raise ValueError("Empty or invalid suggestions list")

        logger.info(
            "[LLM 추천] LLM이 %d개 책 후보 생성: %s ... (외 %d개)",
            len(suggestions),
            [s.get("title") for s in suggestions[:3]],
            max(0, len(suggestions) - 3),
        )
        return suggestions[:num_suggestions]

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("[LLM 추천] LLM이 유효하지 않은 응답 반환: %s, 폴백 사용", e)
        return _fallback_suggestions(top_genres, preferred, disliked)
    except Exception:
        logger.exception("[LLM 추천] LLM 책 후보 생성 실패, 폴백 사용")
        return _fallback_suggestions(top_genres, preferred, disliked)


def _fallback_suggestions(
    top_genres: list[str],
    preferred: list[str],
    disliked: list[str],
) -> list[dict]:
    """LLM 생성 실패 시 장르 기반 폴백 제안 목록 생성 (알라딘 검색 키워드용)."""
    disliked_set = {g.lower() for g in disliked}
    suggestions = []

    candidates = top_genres + [g for g in preferred if g not in top_genres]
    for genre in candidates:
        if genre.lower() not in disliked_set and len(suggestions) < 5:
            suggestions.append({
                "title": genre,
                "author": "",
                "reason_hint": f"선호 장르인 {genre} 기반 추천",
                "_is_keyword_fallback": True,
            })

    if not suggestions:
        suggestions.append({
            "title": "베스트셀러",
            "author": "",
            "reason_hint": "인기 도서 기반 추천",
            "_is_keyword_fallback": True,
        })

    return suggestions


# ──────────────────────────────────────────────
# 4단계: 알라딘 퍼지 매칭 검증 (NEW)
# ──────────────────────────────────────────────

def _fuzzy_score(suggestion: dict, aladin_item) -> float:
    """LLM 제안과 알라딘 결과 간 제목+저자 퍼지 매칭 점수 계산.

    제목 70% + 저자 30% 가중 합산.
    저자 정보가 없는 경우 제목 점수만 사용.
    """
    title_score = SequenceMatcher(
        None,
        suggestion["title"].strip().lower(),
        (aladin_item.title or "").strip().lower(),
    ).ratio()

    suggestion_author = suggestion.get("author", "").strip().lower()
    aladin_author = (aladin_item.author or "").strip().lower()

    if suggestion_author and aladin_author:
        author_score = SequenceMatcher(
            None, suggestion_author, aladin_author
        ).ratio()
        return title_score * _FUZZY_TITLE_WEIGHT + author_score * _FUZZY_AUTHOR_WEIGHT
    else:
        # 저자 정보 없으면 제목 점수만 사용
        return title_score


async def _validate_single_suggestion(
    suggestion: dict,
    exclude_isbn_set: set[str],
) -> dict | None:
    """단일 LLM 제안을 알라딘 API로 검증.

    검증 통과 시 알라딘 결과 데이터 반환 (DB 저장 없음).
    폴백 키워드 제안인 경우 알라딘 첫 번째 결과 반환.
    """
    is_keyword_fallback = suggestion.get("_is_keyword_fallback", False)

    # 폴백 키워드 제안: 제목을 검색 키워드로 사용
    if is_keyword_fallback:
        query = suggestion["title"]
    else:
        query = f"{suggestion['title']} {suggestion.get('author', '')}".strip()

    try:
        results = await aladin_search(query, max_results=_MAX_ALADIN_RESULTS_PER_SUGGESTION)
    except Exception:
        logger.warning("[알라딘 검증] 검색 실패: '%s'", query)
        return None

    if not results:
        logger.debug("[알라딘 검증] 검색 결과 없음: '%s'", query)
        return None

    if is_keyword_fallback:
        # 폴백 키워드: 설명 있는 첫 번째 결과 사용
        for item in results:
            if item.description and (not item.isbn or item.isbn not in exclude_isbn_set):
                return {
                    "title": item.title,
                    "author": item.author or "",
                    "isbn": item.isbn or "",
                    "description": item.description,
                    "cover_image_url": item.cover_image_url or "",
                    "genre": item.genre or "",
                    "reason_hint": suggestion.get("reason_hint", ""),
                }
        return None

    # 일반 LLM 제안: 퍼지 매칭으로 검증
    best_item = None
    best_score = 0.0

    for item in results:
        if not item.description:
            continue
        if item.isbn and item.isbn in exclude_isbn_set:
            continue

        score = _fuzzy_score(suggestion, item)
        if score > best_score:
            best_score = score
            best_item = item

    if best_item is None or best_score < _FUZZY_THRESHOLD:
        logger.debug(
            "[알라딘 검증] 검증 탈락: '%s' (최고 점수=%.2f < %.2f)",
            suggestion["title"], best_score, _FUZZY_THRESHOLD,
        )
        return None

    logger.debug(
        "[알라딘 검증] 검증 통과: '%s' → '%s' (점수=%.2f)",
        suggestion["title"], best_item.title, best_score,
    )
    return {
        "title": best_item.title,
        "author": best_item.author or "",
        "isbn": best_item.isbn or "",
        "description": best_item.description,
        "cover_image_url": best_item.cover_image_url or "",
        "genre": best_item.genre or "",
        "reason_hint": suggestion.get("reason_hint", ""),
    }


_ALADIN_CONCURRENCY_LIMIT = 5  # 동시 알라딘 API 요청 수 제한


async def validate_suggestions_against_aladin(
    suggestions: list[dict],
    exclude_isbn_set: set[str],
) -> list[dict]:
    """LLM 생성 책 후보 목록을 알라딘 API로 병렬 검증.

    DB 저장 없이 실존 여부만 확인.
    검증 통과한 후보만 반환 (중복 ISBN 제거 포함).
    Semaphore로 동시 요청 수를 제한하여 API 과부하 방지.
    """
    logger.info("[알라딘 검증] %d개 후보 병렬 검증 시작 (동시 요청 제한: %d)",
                len(suggestions), _ALADIN_CONCURRENCY_LIMIT)

    semaphore = asyncio.Semaphore(_ALADIN_CONCURRENCY_LIMIT)

    async def bounded_validate(suggestion: dict) -> dict | None:
        """Semaphore로 동시 요청 수를 제한한 검증 래퍼."""
        async with semaphore:
            return await _validate_single_suggestion(suggestion, exclude_isbn_set)

    tasks = [bounded_validate(suggestion) for suggestion in suggestions]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    validated: list[dict] = []
    seen_isbns: set[str] = set()
    seen_titles: set[str] = set()
    exception_count = 0

    for result in results:
        if isinstance(result, Exception):
            exception_count += 1
            logger.debug("[알라딘 검증] 개별 검증 예외: %s", result)
            continue
        if result is None:
            continue

        # ISBN 기준 중복 제거
        isbn = result.get("isbn", "")
        title_key = result["title"].strip().lower()

        if isbn and isbn in seen_isbns:
            continue
        if title_key in seen_titles:
            continue

        if isbn:
            seen_isbns.add(isbn)
        seen_titles.add(title_key)
        validated.append(result)

    if exception_count > 0:
        logger.warning(
            "[알라딘 검증] %d/%d개 검증 중 예외 발생",
            exception_count, len(suggestions),
        )

    logger.info(
        "[알라딘 검증] 검증 완료: %d/%d개 통과",
        len(validated), len(suggestions),
    )
    return validated


# ──────────────────────────────────────────────
# 5단계: KNN 취향 벡터 기반 재랭킹
# ──────────────────────────────────────────────

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


async def _rank_by_preference_vector(
    candidates: list[dict],
    pref_vector: list[float] | None,
    limit: int,
) -> list[dict]:
    """취향 벡터 기반으로 후보를 재랭킹 후 상위 limit개 반환.

    pref_vector가 None이면 알라딘 결과 순서(검증 통과 순서) 그대로 사용.
    각 후보의 description을 임베딩하여 취향 벡터와 cosine similarity 계산.
    """
    if pref_vector is None or not candidates:
        logger.info("[KNN 재랭킹] 취향 벡터 없음 → 알라딘 결과 순서 그대로 사용")
        return candidates[:limit]

    logger.info("[KNN 재랭킹] %d개 후보를 취향 벡터로 재랭킹 시작", len(candidates))

    pref_arr = np.array(pref_vector)
    scored: list[tuple[float, dict]] = []

    for candidate in candidates:
        description = candidate.get("description", "")
        title = candidate.get("title", "")
        author = candidate.get("author", "")

        if not description:
            scored.append((0.0, candidate))
            continue

        text = f"{title} | 저자: {author} | {description}"
        try:
            emb, _ = await embed_text(text)
            emb_arr = np.array(emb)
            # cosine similarity (두 벡터 모두 정규화되어 있으면 내적 = cosine)
            sim = float(np.dot(pref_arr, emb_arr))
            scored.append((sim, candidate))
        except Exception:
            logger.warning("[KNN 재랭킹] 임베딩 실패: '%s'", title)
            scored.append((0.0, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)

    ranked = []
    for score, candidate in scored[:limit]:
        ranked.append({**candidate, "score": round(score, 4)})

    logger.info("[KNN 재랭킹] 재랭킹 완료: 상위 %d개 선택", len(ranked))
    return ranked


# ──────────────────────────────────────────────
# 6단계: 최종 선택 후 DB 저장
# ──────────────────────────────────────────────

async def _save_final_books_to_db(
    db: AsyncSession,
    final_candidates: list[dict],
) -> list[dict]:
    """최종 선택된 책만 DB에 저장하고 book_id를 첨부하여 반환.

    이미 DB에 있는 책은 재사용하고, 없는 책만 새로 저장.
    추천 후보 단계에서 저장하지 않고 최종 결정 이후에만 저장.
    """
    # 기존 도서 조회
    all_books_result = await db.execute(select(Book))
    all_books = all_books_result.scalars().all()
    isbn_to_book: dict[str, Book] = {b.isbn: b for b in all_books if b.isbn}
    title_author_to_book: dict[tuple[str, str], Book] = {
        (b.title.strip().lower(), (b.author or "").strip().lower()): b
        for b in all_books
    }

    result_with_ids: list[dict] = []

    for candidate in final_candidates:
        isbn = candidate.get("isbn", "")
        title_key = (
            candidate["title"].strip().lower(),
            candidate.get("author", "").strip().lower(),
        )

        # ISBN으로 기존 도서 찾기
        if isbn and isbn in isbn_to_book:
            existing = isbn_to_book[isbn]
            logger.debug("[DB 저장] 기존 도서 재사용 (ISBN): '%s'", candidate["title"])
            result_with_ids.append({**candidate, "book_id": str(existing.id)})
            continue

        # 제목+저자로 기존 도서 찾기
        if title_key in title_author_to_book:
            existing = title_author_to_book[title_key]
            logger.debug("[DB 저장] 기존 도서 재사용 (제목+저자): '%s'", candidate["title"])
            result_with_ids.append({**candidate, "book_id": str(existing.id)})
            continue

        # 새 도서: DB에 저장 + OpenSearch 인덱싱
        book = Book(
            title=candidate["title"][:_MAX_TITLE],
            author=(candidate.get("author") or "")[:_MAX_AUTHOR],
            isbn=isbn or None,
            description=candidate.get("description"),
            cover_image_url=(candidate.get("cover_image_url") or "")[:_MAX_COVER_URL],
            genre=(candidate.get("genre") or "")[:_MAX_GENRE],
        )
        db.add(book)
        try:
            await db.flush()
        except Exception:
            logger.error("[DB 저장] DB flush 실패, 해당 도서 건너뜀: '%s'", candidate["title"])
            db.expunge(book)
            continue

        logger.info("[DB 저장] 최종 추천 신규 도서 저장: '%s'", book.title)

        if isbn:
            isbn_to_book[isbn] = book
        title_author_to_book[title_key] = book

        result_with_ids.append({**candidate, "book_id": str(book.id)})

    return result_with_ids


# ──────────────────────────────────────────────
# 7단계: 추천 이유 생성
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
        f"추천 도서: {recommended_book['title']} (저자: {recommended_book.get('author', '')})\n"
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
# 메인: get_recommendations
# ──────────────────────────────────────────────

async def get_recommendations(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 10,
    force_refresh: bool = False,
) -> list[dict]:
    """LLM 책 후보 생성 → 알라딘 실존 검증 → KNN 재랭킹 파이프라인.

    1. 캐시 확인
    2. 유저 서재 로드
    3. 취향 분석 (캐싱)
    4. 유저 요약 생성
    5. LLM으로 책 후보 생성 (limit * 2.5개)
    6. 알라딘 실존 검증 (DB 저장 없음)
    7. 취향 벡터 기반 재랭킹 → 상위 limit개 선택
    8. 최종 선택된 책만 DB 저장 (최대 limit개)
    9. 추천 이유 생성 + Recommendation 레코드 저장 + 캐시 반환
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
    user_book_isbns = {ub.book.isbn for ub in user_books if ub.book and ub.book.isbn}

    # 서재가 비어있으면 베스트셀러 기반 기본 추천
    if not user_books:
        logger.info("[recommend] 서재 비어있음, 베스트셀러 폴백 사용")
        return await _bestseller_fallback(db, user_id, limit)

    # 3. 취향 분석 (캐싱)
    memo_analysis = await get_memo_analysis(user_id, user_books)
    user_preferences = memo_analysis.get("preferences", "")

    # 4. 유저 요약 생성
    user_summary = _build_user_summary(user_books)

    # 5. LLM으로 책 후보 생성 (최종 결과의 2.5배)
    top_genres = _extract_top_genres(user_books)
    num_suggestions = int(limit * 2.5)
    suggestions = await generate_book_suggestions(
        user_summary, memo_analysis, top_genres, num_suggestions=num_suggestions
    )
    logger.info("[recommend] LLM 추천 후보 %d개 생성", len(suggestions))

    # 6. 알라딘 실존 검증 (DB 저장 없음)
    validated = await validate_suggestions_against_aladin(
        suggestions, exclude_isbn_set=user_book_isbns
    )
    logger.info("[recommend] 알라딘 검증 통과: %d개", len(validated))

    # 검증 통과 후보가 부족할 경우 폴백
    if len(validated) < limit:
        logger.info(
            "[recommend] 검증 통과 후보 부족 (%d < %d), 장르 키워드 폴백 추가",
            len(validated), limit,
        )
        fallback = _fallback_suggestions(top_genres,
                                         memo_analysis.get("preferred_genres", []),
                                         memo_analysis.get("disliked_genres", []))
        extra = await validate_suggestions_against_aladin(
            fallback, exclude_isbn_set=user_book_isbns
        )
        # 중복 제거 후 병합
        existing_titles = {v["title"].strip().lower() for v in validated}
        for item in extra:
            if item["title"].strip().lower() not in existing_titles:
                validated.append(item)
                existing_titles.add(item["title"].strip().lower())

    if not validated:
        logger.info("[recommend] 후보 없음, 빈 결과 반환")
        return []

    # 7. 취향 벡터 기반 재랭킹 → 상위 limit개 선택
    pref_vector = await compute_user_preference_vector(db, user_id)
    ranked = await _rank_by_preference_vector(validated, pref_vector, limit=limit)
    logger.info("[recommend] 재랭킹 후 최종 후보: %d개", len(ranked))

    if not ranked:
        return []

    # 8 & 9. 최종 선택된 책 DB 저장 + 추천 이유 생성 + Recommendation 레코드 저장
    try:
        final_with_ids = await _save_final_books_to_db(db, ranked)

        recommendations = []
        await db.execute(
            delete(Recommendation).where(Recommendation.user_id == user_id)
        )

        for item in final_with_ids:
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
                "author": item.get("author", ""),
                "description": item.get("description", ""),
                "genre": item.get("genre", ""),
                "cover_image_url": item.get("cover_image_url", ""),
                "score": item.get("score", 0.0),
                "reason": reason,
            })

        await db.commit()
    except Exception:
        logger.exception("[recommend] DB 저장/커밋 실패, 롤백 실행")
        await db.rollback()
        raise

    # 캐시 업데이트
    _recommendation_cache[user_id] = (datetime.now(timezone.utc), recommendations)

    logger.info("[recommend] === 파이프라인 완료: %d건 추천 생성 ===", len(recommendations))
    return recommendations


# ──────────────────────────────────────────────
# 서재 비어있는 유저 폴백
# ──────────────────────────────────────────────

async def _bestseller_fallback(
    db: AsyncSession,
    user_id: UUID,
    limit: int,
) -> list[dict]:
    """서재가 비어있는 유저를 위한 베스트셀러 기반 기본 추천.

    LLM 없이 알라딘 베스트셀러 직접 검색 → 검증 없이 반환.
    DB 저장은 최종 선택 후에만 수행.
    """
    logger.info("[폴백] 베스트셀러 기반 추천 시작")

    fallback_keywords = ["베스트셀러", "올해의 책"]
    all_results: list[dict] = []
    seen_isbns: set[str] = set()

    for keyword in fallback_keywords:
        try:
            items = await aladin_search(keyword, max_results=limit)
            for item in items:
                if not item.description:
                    continue
                isbn = item.isbn or ""
                if isbn and isbn in seen_isbns:
                    continue
                if isbn:
                    seen_isbns.add(isbn)
                all_results.append({
                    "title": item.title,
                    "author": item.author or "",
                    "isbn": isbn,
                    "description": item.description,
                    "cover_image_url": item.cover_image_url or "",
                    "genre": item.genre or "",
                    "reason_hint": "많은 독자들에게 사랑받는 인기 도서",
                    "score": 0.0,
                })
        except Exception:
            logger.warning("[폴백] 알라딘 검색 실패: '%s'", keyword)

    if not all_results:
        return []

    final_candidates = all_results[:limit]
    final_with_ids = await _save_final_books_to_db(db, final_candidates)

    recommendations = []
    await db.execute(
        delete(Recommendation).where(Recommendation.user_id == user_id)
    )

    for item in final_with_ids:
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
            "author": item.get("author", ""),
            "description": item.get("description", ""),
            "genre": item.get("genre", ""),
            "cover_image_url": item.get("cover_image_url", ""),
            "score": 0.0,
            "reason": reason,
        })

    if recommendations:
        await db.commit()
        _recommendation_cache[user_id] = (datetime.now(timezone.utc), recommendations)

    logger.info("[폴백] 베스트셀러 추천 %d건 생성", len(recommendations))
    return recommendations
