"""
커뮤니티 데이터에서 책 제목을 추출하여 books DB에 시딩.

파서 4개에서 book_title 메타데이터를 수집 → 알라딘 실존 검증 → books DB 저장.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.services.aladin import search_books as aladin_search
from app.services.rag_pipeline.parsers.recommend_parser import RecommendParser
from app.services.rag_pipeline.parsers.book_reviews_parser import BookReviewsParser
from app.services.rag_pipeline.parsers.monthly_closing_parser import MonthlyClosingParser
from app.services.rag_pipeline.parsers.thread_reviews_parser import ThreadReviewsParser

logger = logging.getLogger(__name__)

# 알라딘 검증 설정
_FUZZY_THRESHOLD = 0.7            # 제목 유사도 임계값
_ALADIN_MAX_RESULTS = 1           # 검증용 알라딘 검색 결과 수
_SEMAPHORE_LIMIT = 5              # 동시 알라딘 API 요청 제한

# Book 모델 컬럼 길이 제한
_MAX_TITLE = 500
_MAX_AUTHOR = 1000
_MAX_GENRE = 500
_MAX_COVER_URL = 500

# 소스별 파일명 매핑
SOURCE_FILES = {
    "recommend": "recommend.md",
    "reviews": "book_reviews.json",
    "monthly_closing": "monthly_closing_best.md",
    "thread_reviews": "thread_review.json",
}


@dataclass
class CommunitySeedResult:
    """커뮤니티 시딩 결과."""
    total: int = 0       # 추출된 고유 책 제목 수
    seeded: int = 0      # DB에 새로 저장된 책 수
    skipped: int = 0     # 이미 존재하거나 검증 실패한 책 수
    errors: int = 0      # 에러 발생 수


def _title_similarity(a: str, b: str) -> float:
    """두 제목의 유사도 계산 (0.0 ~ 1.0)."""
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def _extract_book_titles_from_parsers(data_dir: Path) -> set[str]:
    """4개 파서에서 book_title 메타데이터를 수집하여 고유 제목 집합 반환."""
    parsers = {
        "recommend": RecommendParser(),
        "reviews": BookReviewsParser(),
        "monthly_closing": MonthlyClosingParser(),
        "thread_reviews": ThreadReviewsParser(),
    }

    titles: set[str] = set()

    for source_name, parser in parsers.items():
        file_name = SOURCE_FILES.get(source_name)
        if not file_name:
            continue

        file_path = data_dir / file_name
        if not file_path.exists():
            logger.warning("[community-seeder] File not found: %s", file_path)
            continue

        try:
            chunks = parser.parse(str(file_path))
            for chunk in chunks:
                book_title = chunk.metadata.get("book_title", "").strip()
                if book_title:
                    titles.add(book_title)
            logger.info(
                "[community-seeder] %s: extracted titles (cumulative=%d)",
                source_name, len(titles),
            )
        except Exception as e:
            logger.error("[community-seeder] Failed to parse %s: %s", source_name, e)

    return titles


async def _validate_and_fetch(title: str, semaphore: asyncio.Semaphore):
    """알라딘에서 제목을 검색하여 유사도 기준 검증된 책 반환.

    Returns:
        알라딘 BookSearchResult 또는 None
    """
    async with semaphore:
        try:
            results = await aladin_search(title, max_results=_ALADIN_MAX_RESULTS)
            if not results:
                return None

            best = results[0]
            similarity = _title_similarity(title, best.title)

            if similarity >= _FUZZY_THRESHOLD:
                logger.debug(
                    "[community-seeder] Validated '%s' → '%s' (sim=%.2f)",
                    title, best.title, similarity,
                )
                return best

            logger.debug(
                "[community-seeder] Rejected '%s' → '%s' (sim=%.2f < %.2f)",
                title, best.title, similarity, _FUZZY_THRESHOLD,
            )
        except Exception as e:
            logger.warning("[community-seeder] Aladin search failed for '%s': %s", title, e)

    return None


async def seed_books_from_community(
    db: AsyncSession,
    data_dir: Path = Path("/app/output"),
) -> CommunitySeedResult:
    """커뮤니티 데이터에서 책을 추출하여 books DB에 시딩.

    Args:
        db: 비동기 DB 세션
        data_dir: 커뮤니티 데이터 파일 경로

    Returns:
        CommunitySeedResult (total, seeded, skipped, errors)
    """
    result = CommunitySeedResult()

    # 1단계: 파서에서 책 제목 추출
    titles = _extract_book_titles_from_parsers(data_dir)
    result.total = len(titles)
    logger.info("[community-seeder] Extracted %d unique book titles", result.total)

    if not titles:
        return result

    # 2단계: 기존 DB 책 목록 조회 (중복 체크용)
    all_books_result = await db.execute(select(Book))
    all_books = all_books_result.scalars().all()
    existing_isbns: set[str] = {b.isbn for b in all_books if b.isbn}
    existing_title_author: set[tuple[str, str]] = {
        (b.title.strip().lower(), (b.author or "").strip().lower())
        for b in all_books
    }

    # 3단계: DB에 이미 존재하는 title 사전 필터링 (알라딘 API 호출 절약)
    # existing_title_author의 첫 번째 요소(title)만으로 비교하여 빠르게 제외
    existing_titles_lower: set[str] = {t.strip().lower() for t, _ in existing_title_author}
    titles_to_validate = {
        title for title in titles
        if title.strip().lower() not in existing_titles_lower
    }
    pre_filtered = len(titles) - len(titles_to_validate)
    if pre_filtered > 0:
        logger.info(
            "[community-seeder] DB 중복 사전 필터링: %d개 제외, 알라딘 검증 대상: %d개",
            pre_filtered, len(titles_to_validate),
        )

    # 4단계: 알라딘 실존 검증 (동시 요청 제한, 사전 필터링된 titles만 검증)
    semaphore = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    validation_tasks = [_validate_and_fetch(title, semaphore) for title in titles_to_validate]
    validated_items = await asyncio.gather(*validation_tasks, return_exceptions=True)

    # 5단계: 검증 통과한 책 DB 저장
    for item in validated_items:
        if item is None or isinstance(item, Exception):
            result.skipped += 1
            continue

        # ISBN 중복 체크
        if item.isbn and item.isbn in existing_isbns:
            logger.debug("[community-seeder] Skip duplicate ISBN: %s", item.isbn)
            result.skipped += 1
            continue

        # 제목+저자 중복 체크
        title_key = (item.title.strip().lower(), (item.author or "").strip().lower())
        if title_key in existing_title_author:
            logger.debug("[community-seeder] Skip duplicate title+author: %s", item.title)
            result.skipped += 1
            continue

        # description 없으면 스킵 (임베딩 품질 보장)
        if not item.description:
            logger.debug("[community-seeder] Skip no-description book: %s", item.title)
            result.skipped += 1
            continue

        try:
            book = Book(
                title=(item.title or "")[:_MAX_TITLE],
                author=(item.author or "")[:_MAX_AUTHOR],
                isbn=item.isbn,
                description=item.description,
                cover_image_url=(item.cover_image_url or "")[:_MAX_COVER_URL],
                genre=(item.genre or "")[:_MAX_GENRE],
                published_at=item.published_at,
            )
            db.add(book)
            await db.flush()

            if item.isbn:
                existing_isbns.add(item.isbn)
            existing_title_author.add(title_key)

            result.seeded += 1
            logger.info("[community-seeder] Seeded '%s' by %s", item.title, item.author)

        except Exception as e:
            logger.error("[community-seeder] Failed to seed '%s': %s", item.title, e)
            result.errors += 1

    if result.seeded > 0:
        await db.commit()

    # 사전 필터링(DB 중복 제외)된 수를 skipped에 합산
    result.skipped += pre_filtered

    logger.info(
        "[community-seeder] Done: total=%d seeded=%d skipped=%d errors=%d",
        result.total, result.seeded, result.skipped, result.errors,
    )
    return result
