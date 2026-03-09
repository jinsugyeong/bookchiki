"""추천 서비스: OpenSearch 하이브리드 검색 기반 파이프라인.

1. is_dirty 확인 → 캐시 히트 시 DB 직접 조회 (ISBN 이중 필터)
2. user_books 인덱스에서 취향 벡터 계산 (평점가중 책임베딩 + 메모임베딩)
3. books 인덱스 하이브리드 검색 (BM25 + k-NN) or cold start
4. 알라딘 실시간 보완 (항상 _ALADIN_SLOTS개 슬롯 확보)
5. CF 앙상블 스코어링 (ALS 모델 있을 때만)
6. 다양성 보장 + 매칭률 정규화
7. LLM 추천 이유 병렬 생성 (asyncio.gather)
8. recommendations 테이블 저장 + user_preference_profiles 갱신
"""

import asyncio
import logging
import random
from collections import Counter
from uuid import UUID

import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.user_book import UserBook
from app.models.recommendation import Recommendation
from app.models.user_dismissed_book import UserDismissedBook
from app.services.user_book_indexer import get_user_book_interactions
from app.services.book_search import search_books_hybrid, search_books_cold_start
from app.services.aladin_supplement import supplement_with_aladin
from app.services.profile_cache import (
    update_profile,
    is_recommendation_fresh,
)
from app.services.cf_scorer import cf_scorer

logger = logging.getLogger(__name__)

_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# ── 상수 ──────────────────────────────────────
_BOOK_EMBEDDING_ALPHA = 0.6
_MEMO_EMBEDDING_ALPHA = 0.4

_CF_ALPHA_THRESHOLDS: list[tuple[int, float]] = [
    (10, 0.9),
    (30, 0.7),
]
_CF_ALPHA_DEFAULT = 0.5

_MAX_SAME_GENRE = 2
_SCORE_NOISE_STD = 0.03

_SCORE_MIN_OUT = 0.80
_SCORE_MAX_OUT = 1.00

# 알라딘 보완: 항상 최소 이 수만큼 DB 밖 책 확보 시도
_ALADIN_SLOTS = 2


# ── Exclude 집합 구성 ─────────────────────────

class _ExcludeSet:
    """서재 + dismissed 책의 book_id / ISBN 집합."""

    def __init__(
        self,
        book_ids: set[str],
        isbns: set[str],
    ):
        self.book_ids = book_ids
        self.isbns = isbns

    @property
    def book_id_list(self) -> list[str]:
        return list(self.book_ids)

    def contains(self, book_id: str, isbn: str) -> bool:
        """book_id 또는 ISBN으로 제외 대상인지 판별."""
        if book_id in self.book_ids:
            return True
        if isbn and isbn in self.isbns:
            return True
        return False


async def _build_exclude_set(
    db: AsyncSession,
    user_id: UUID,
    user_books: list[UserBook],
) -> _ExcludeSet:
    """서재 + dismissed 책에서 exclude book_ids/isbns 수집."""
    # 서재 book_id + ISBN
    library_ids = {str(ub.book_id) for ub in user_books}
    library_isbns = {
        ub.book.isbn for ub in user_books if ub.book and ub.book.isbn
    }

    # dismissed book_id + ISBN (book 관계 조인)
    dismissed_result = await db.execute(
        select(UserDismissedBook)
        .options(joinedload(UserDismissedBook.book))
        .where(UserDismissedBook.user_id == user_id)
    )
    dismissed_list = dismissed_result.unique().scalars().all()
    dismissed_ids = {str(d.book_id) for d in dismissed_list}
    dismissed_isbns = {
        d.book.isbn for d in dismissed_list if d.book and d.book.isbn
    }

    all_ids = library_ids | dismissed_ids
    all_isbns = library_isbns | dismissed_isbns

    logger.info(
        "[recommend] exclude 구성: library=%d(%d isbn) dismissed=%d(%d isbn) → ids=%d isbns=%d",
        len(library_ids), len(library_isbns),
        len(dismissed_ids), len(dismissed_isbns),
        len(all_ids), len(all_isbns),
    )
    return _ExcludeSet(book_ids=all_ids, isbns=all_isbns)


# ── CF 앙상블 ─────────────────────────────────

def _compute_ensemble_alpha(book_count: int) -> float:
    """서재 책 수에 따른 앙상블 alpha 반환."""
    for threshold, alpha in _CF_ALPHA_THRESHOLDS:
        if book_count < threshold:
            return alpha
    return _CF_ALPHA_DEFAULT


def _apply_cf_ensemble(
    candidates: list[dict],
    user_id: UUID,
    book_count: int,
) -> list[dict]:
    """CF 점수를 OpenSearch 점수와 앙상블하여 후보 재정렬."""
    if not cf_scorer.is_available():
        logger.debug("[recommend] CF 모델 없음 → OpenSearch 점수만 사용")
        return candidates

    candidate_book_ids = [c["book_id"] for c in candidates]
    cf_scores = cf_scorer.get_scores(user_id, candidate_book_ids)

    if not cf_scores:
        logger.debug("[recommend] CF 매핑 없음 (user=%s) → OpenSearch 점수만 사용", user_id)
        return candidates

    alpha = _compute_ensemble_alpha(book_count)
    logger.info(
        "[recommend] CF 앙상블: user=%s books=%d alpha=%.2f cf_matched=%d/%d",
        user_id, book_count, alpha, len(cf_scores), len(candidates),
    )

    updated = []
    for c in candidates:
        os_score = c.get("score", 0.0)
        cf_score = cf_scores.get(c["book_id"], 0.0)
        ensemble_score = alpha * os_score + (1 - alpha) * cf_score
        updated.append({**c, "score": round(ensemble_score, 6)})

    updated.sort(key=lambda x: x["score"], reverse=True)
    return updated


# ── 다양성 + 정규화 ───────────────────────────

def _extract_leaf_genre(genre: str | None) -> str:
    """알라딘 장르 계층(A>B>C)에서 최말단 장르 반환."""
    if not genre:
        return ""
    return genre.split(">")[-1].strip()


def _diversify_candidates(candidates: list[dict], limit: int) -> list[dict]:
    """장르 다양성 보장 + score 노이즈로 매번 다른 추천 생성."""
    noisy = []
    for c in candidates:
        noise = random.gauss(0, _SCORE_NOISE_STD)
        noisy.append({**c, "score": round(c.get("score", 0.0) + noise, 6)})

    noisy.sort(key=lambda x: x["score"], reverse=True)

    if len(noisy) <= limit:
        logger.info("[recommend] 후보 부족(%d≤%d) → 다양성 건너뜀", len(noisy), limit)
        return noisy

    genre_counts: Counter = Counter()
    selected = []
    deferred = []

    for c in noisy:
        leaf_genre = _extract_leaf_genre(c.get("genre", ""))
        if leaf_genre and genre_counts[leaf_genre] >= _MAX_SAME_GENRE:
            deferred.append(c)
            continue
        if leaf_genre:
            genre_counts[leaf_genre] += 1
        selected.append(c)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        seen_ids = {c["book_id"] for c in selected}
        for c in deferred:
            if c["book_id"] not in seen_ids:
                selected.append(c)
                if len(selected) >= limit:
                    break

    logger.info(
        "[recommend] 다양성 적용: %d → %d권 (장르: %s)",
        len(candidates), len(selected), dict(genre_counts.most_common(3)),
    )
    return selected


def _normalize_scores(candidates: list[dict]) -> list[dict]:
    """추천 결과 score를 [0.80, 1.00] 범위로 min-max 정규화."""
    if not candidates:
        return candidates

    scores = [c.get("score", 0.0) for c in candidates]
    min_s, max_s = min(scores), max(scores)

    if max_s == min_s:
        return [{**c, "score": _SCORE_MAX_OUT} for c in candidates]

    return [
        {
            **c,
            "score": round(
                _SCORE_MIN_OUT
                + (c.get("score", 0.0) - min_s) / (max_s - min_s)
                * (_SCORE_MAX_OUT - _SCORE_MIN_OUT),
                3,
            ),
        }
        for c in candidates
    ]


# ── 취향 벡터 계산 ────────────────────────────

async def _compute_preference_vector(user_id: UUID) -> list[float] | None:
    """user_books 인덱스에서 취향 벡터 계산.

    preference_vector = α × 평점가중_책임베딩 + (1-α) × 메모평균_임베딩 (α=0.6)
    """
    interactions = await get_user_book_interactions(user_id)
    if not interactions:
        logger.info("[recommend] No interactions for user %s (cold start)", user_id)
        return None

    book_embeddings: list[list[float]] = []
    book_weights: list[float] = []
    memo_embeddings: list[list[float]] = []

    for interaction in interactions:
        book_emb = interaction.get("book_embedding")
        if not book_emb:
            continue
        rating = interaction.get("rating")
        weight = (rating / 5.0) if rating else 0.5
        book_embeddings.append(book_emb)
        book_weights.append(weight)
        memo_emb = interaction.get("memo_embedding")
        if memo_emb:
            memo_embeddings.append(memo_emb)

    if not book_embeddings:
        logger.info("[recommend] No book embeddings for user %s (cold start)", user_id)
        return None

    arr = np.array(book_embeddings)
    w = np.array(book_weights).reshape(-1, 1)
    weighted_book = (arr * w).sum(axis=0) / w.sum()

    if memo_embeddings:
        memo_avg = np.mean(np.array(memo_embeddings), axis=0)
        combined = _BOOK_EMBEDDING_ALPHA * weighted_book + _MEMO_EMBEDDING_ALPHA * memo_avg
    else:
        combined = weighted_book

    norm = np.linalg.norm(combined)
    if norm > 0:
        combined = combined / norm

    logger.info(
        "[recommend] Preference vector computed: user=%s books=%d memos=%d",
        user_id, len(book_embeddings), len(memo_embeddings),
    )
    return combined.tolist()


# ── 프로필 데이터 구성 ─────────────────────────

def _build_profile_data(user_books: list[UserBook]) -> dict:
    """로드된 user_books에서 profile_data 구성."""
    genre_counter: Counter[str] = Counter()
    author_counter: Counter[str] = Counter()

    for ub in user_books:
        if not ub.book:
            continue
        if ub.book.genre:
            last_genre = ub.book.genre.split(">")[-1].strip()
            if last_genre:
                genre_counter[last_genre] += 1
        if ub.book.author and ub.rating and ub.rating >= 4:
            author_counter[ub.book.author] += 1

    preferred_genres = [g for g, _ in genre_counter.most_common(5)]
    preferred_authors = [a for a, _ in author_counter.most_common(3)]

    rated = [ub for ub in user_books if ub.rating is not None and ub.book]
    rated.sort(key=lambda x: x.rating or 0, reverse=True)
    top_rated_books = [
        {"title": ub.book.title, "author": ub.book.author or "", "rating": ub.rating}
        for ub in rated[:10]
    ]

    return {
        "preferred_genres": preferred_genres,
        "preferred_authors": preferred_authors,
        "disliked_genres": [],
        "preference_summary": "",
        "top_rated_books": top_rated_books,
        "reading_count": len(user_books),
    }


# ── DB 캐시 조회 ──────────────────────────────

async def _load_cached_recommendations(
    db: AsyncSession,
    user_id: UUID,
    limit: int,
) -> list[dict]:
    """recommendations 테이블에서 캐시된 추천 조회.

    서재(wishlist 포함) + dismissed 책은 book_id + ISBN 이중 필터로 제외.
    """
    # 서재 전체 조회 (book_id + ISBN)
    ub_result = await db.execute(
        select(UserBook).options(joinedload(UserBook.book)).where(UserBook.user_id == user_id)
    )
    ub_list = ub_result.unique().scalars().all()
    library_ids = {ub.book_id for ub in ub_list}
    library_isbns = {ub.book.isbn for ub in ub_list if ub.book and ub.book.isbn}

    # dismissed 전체 조회 (book_id + ISBN)
    dismissed_result = await db.execute(
        select(UserDismissedBook)
        .options(joinedload(UserDismissedBook.book))
        .where(UserDismissedBook.user_id == user_id)
    )
    dismissed_list = dismissed_result.unique().scalars().all()
    dismissed_ids = {d.book_id for d in dismissed_list}
    dismissed_isbns = {d.book.isbn for d in dismissed_list if d.book and d.book.isbn}

    exclude_ids = library_ids | dismissed_ids
    exclude_isbns = library_isbns | dismissed_isbns

    # DB 쿼리 (book_id 기반 exclude)
    query = (
        select(Recommendation)
        .options(joinedload(Recommendation.book))
        .where(Recommendation.user_id == user_id)
        .order_by(Recommendation.score.desc())
        .limit(limit * 2)  # ISBN 이중 필터 후 부족 방지
    )
    if exclude_ids:
        query = query.where(Recommendation.book_id.not_in(exclude_ids))

    result = await db.execute(query)
    recs = result.unique().scalars().all()

    # ISBN 이중 필터: 동일 책이 다른 book_id로 중복 저장된 경우
    result_list = []
    for rec in recs:
        if len(result_list) >= limit:
            break
        rec_isbn = rec.book.isbn if rec.book else None
        if rec_isbn and rec_isbn in exclude_isbns:
            logger.info("[recommend] ISBN 이중 필터(cache): isbn='%s' title='%s' 제거",
                        rec_isbn, rec.book.title if rec.book else "?")
            continue
        result_list.append({
            "book_id": str(rec.book_id),
            "title": rec.book.title if rec.book else "",
            "author": rec.book.author if rec.book else "",
            "description": rec.book.description if rec.book else "",
            "genre": rec.book.genre if rec.book else "",
            "cover_image_url": rec.book.cover_image_url if rec.book else "",
            "score": rec.score,
            "reason": rec.reason,
        })

    logger.info(
        "[recommend] Cache HIT filter: ids=%d isbns=%d → %d recs",
        len(exclude_ids), len(exclude_isbns), len(result_list),
    )
    return result_list


# ── 유저 요약 (추천 이유 생성용) ───────────────

def _build_user_summary(user_books: list[UserBook]) -> str:
    """유저의 평점 높은 도서 목록을 텍스트 요약으로 생성."""
    rated_books = [ub for ub in user_books if ub.rating is not None]
    summary_parts = []
    for ub in sorted(rated_books, key=lambda x: x.rating or 0, reverse=True)[:10]:
        if ub.book:
            summary_parts.append(f"- {ub.book.title} ({ub.book.author}) ★{ub.rating}")
    return "\n".join(summary_parts) if summary_parts else "독서 기록 없음"


# ── 추천 이유 생성 (LLM) ──────────────────────

async def generate_recommendation_reason(
    user_books_summary: str,
    recommended_book: dict,
    user_preferences: str = "",
    reason_hint: str = "",
) -> str:
    """GPT-4o-mini를 사용해 한국어 추천 이유 생성."""
    pref_section = f"\n사용자 취향 분석: {user_preferences}\n" if user_preferences else ""
    hint_section = f"\n추천 방향 힌트: {reason_hint}\n" if reason_hint else ""

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
            timeout=10.0,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("[recommend] Failed to generate recommendation reason")
        return "독서 취향 분석을 기반으로 추천된 도서입니다."


# ── 메인: get_recommendations ─────────────────

async def get_recommendations(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 10,
    force_refresh: bool = False,
) -> list[dict]:
    """OpenSearch 하이브리드 검색 + CF 앙상블 기반 추천 파이프라인.

    1. is_dirty 확인 → 캐시 히트 시 DB 직접 조회 (ISBN 이중 필터)
    2. user_books에서 취향 벡터 + 프로필 + exclude 집합 구성
    3. books 인덱스 하이브리드 검색 (or cold start)
    4. 알라딘 실시간 보완 (항상 _ALADIN_SLOTS개 슬롯 확보)
    5. ISBN 이중 필터 후처리
    6. CF 앙상블 + 다양성 + 정규화
    7. LLM 추천 이유 병렬 생성
    8. recommendations 저장 + 프로필 갱신
    """
    # 1. 캐시 확인 (is_dirty 플래그)
    if not force_refresh:
        fresh = await is_recommendation_fresh(db, user_id)
        if fresh:
            cached = await _load_cached_recommendations(db, user_id, limit)
            if cached:
                logger.info(
                    "[recommend] Cache HIT for user %s (%d recs)", user_id, len(cached)
                )
                return cached

    logger.info("[recommend] === 파이프라인 시작 (user=%s, limit=%d) ===", user_id, limit)

    # 2. user_books 한 번만 쿼리
    ub_result = await db.execute(
        select(UserBook)
        .options(joinedload(UserBook.book))
        .where(UserBook.user_id == user_id)
    )
    user_books = ub_result.unique().scalars().all()

    # 3. 취향 벡터 + 프로필 + exclude 집합
    preference_vector = await _compute_preference_vector(user_id)
    profile_data = _build_profile_data(user_books)
    excludes = await _build_exclude_set(db, user_id, user_books)

    # 4. OpenSearch 검색 (ISBN exclude 포함)
    # 알라딘 슬롯 확보를 위해 OpenSearch에서 (limit - _ALADIN_SLOTS)개만 요청
    os_limit = max(limit - _ALADIN_SLOTS, 1)

    if preference_vector is not None:
        candidates = await search_books_hybrid(
            preference_vector=preference_vector,
            genre_keywords=profile_data.get("preferred_genres", []),
            author_keywords=profile_data.get("preferred_authors", []),
            exclude_book_ids=excludes.book_id_list,
            exclude_isbns=excludes.isbns,
            k=os_limit,
        )
    else:
        logger.info("[recommend] Cold start: preference_vector is None")
        candidates = await search_books_cold_start(
            k=os_limit,
            exclude_book_ids=excludes.book_id_list,
            exclude_isbns=excludes.isbns,
        )

    # 5. 알라딘 실시간 보완 (항상 실행 — 나머지 슬롯 알라딘으로 채움)
    if len(candidates) < limit:
        candidates = await supplement_with_aladin(
            db=db,
            candidates=candidates,
            genre_keywords=profile_data.get("preferred_genres", []),
            exclude_book_ids=excludes.book_id_list,
            exclude_isbns=excludes.isbns,
            limit=limit,
        )

    # 5.5 ISBN 이중 필터 후처리 (안전장치)
    before = len(candidates)
    candidates = [
        c for c in candidates
        if not excludes.contains(c["book_id"], c.get("isbn", ""))
    ]
    if len(candidates) < before:
        logger.info("[recommend] ISBN 이중 필터: %d → %d", before, len(candidates))

    if not candidates:
        logger.info("[recommend] No candidates found, returning empty")
        return []

    # 6. CF 앙상블 + 다양성 + 정규화
    candidates = _apply_cf_ensemble(candidates, user_id, len(user_books))
    candidates = _diversify_candidates(candidates, limit)
    candidates = _normalize_scores(candidates)

    # 7. LLM 추천 이유 병렬 생성
    user_summary = _build_user_summary(user_books)
    user_preferences = ", ".join(profile_data.get("preferred_genres", []))

    reasons: list[str] = await asyncio.gather(*[
        generate_recommendation_reason(user_summary, c, user_preferences)
        for c in candidates
    ])

    # 8. 기존 추천 삭제 + 새 추천 저장 + 프로필 갱신
    try:
        await db.execute(
            delete(Recommendation).where(Recommendation.user_id == user_id)
        )

        recommendations = []
        for candidate, reason in zip(candidates, reasons):
            rec = Recommendation(
                user_id=user_id,
                book_id=UUID(candidate["book_id"]),
                score=candidate.get("score", 0.0),
                reason=reason,
            )
            db.add(rec)
            recommendations.append({
                "book_id": candidate["book_id"],
                "title": candidate["title"],
                "author": candidate.get("author", ""),
                "description": candidate.get("description", ""),
                "genre": candidate.get("genre", ""),
                "cover_image_url": candidate.get("cover_image_url", ""),
                "score": candidate.get("score", 0.0),
                "reason": reason,
            })

        await update_profile(db, user_id, profile_data, preference_vector)
        await db.commit()
    except Exception:
        logger.exception("[recommend] Pipeline failed, rolling back")
        await db.rollback()
        raise

    logger.info("[recommend] === 파이프라인 완료: %d건 추천 생성 ===", len(recommendations))
    return recommendations
