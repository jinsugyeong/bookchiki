"""알라딘 실시간 보완 서비스.

추천 결과에 DB 밖 책을 포함시키기 위해 알라딘 API로 보완.
신규 책은 DB + OpenSearch에 저장해 다음 추천부터 캐시됨.
ISBN 기반 중복 검사로 서재/dismissed 책 제외.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.schemas.book import BookSearchResult
from app.services.aladin import search_books as aladin_search
from app.services.book_indexer import index_single_book

logger = logging.getLogger(__name__)

_MAX_TITLE = 500
_MAX_AUTHOR = 1000
_MAX_GENRE = 500
_MAX_COVER_URL = 500


async def _find_existing_book(db: AsyncSession, isbn: str | None, title: str, author: str) -> Book | None:
    """ISBN 우선 → title+author 폴백으로 기존 책 조회."""
    if isbn:
        result = await db.execute(select(Book).where(Book.isbn == isbn))
        book = result.scalar_one_or_none()
        if book:
            return book

    first_author = author.split(",")[0].split("(")[0].strip()
    if title and first_author:
        result = await db.execute(
            select(Book).where(
                Book.title.ilike(title.strip()),
                Book.author.ilike(f"%{first_author}%"),
            )
        )
        return result.scalar_one_or_none()
    return None


async def _save_new_book(db: AsyncSession, item: BookSearchResult) -> Book | None:
    """알라딘 결과를 DB에 저장하고 Book 반환.

    중복 시 기존 Book 반환. 저장 후 OpenSearch 인덱싱은 백그라운드로 실행.
    """
    existing = await _find_existing_book(db, item.isbn, item.title, item.author)
    if existing:
        return existing

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
    try:
        await db.flush()
        await db.commit()
        logger.info("[aladin-supplement] 신규 책 저장: '%s' / %s", book.title, book.author)
    except Exception:
        await db.rollback()
        logger.warning("[aladin-supplement] 책 저장 실패 (중복 가능): '%s'", item.title)
        return None

    asyncio.create_task(_index_book_background(book))
    return book


async def _index_book_background(book: Book) -> None:
    """OpenAI 임베딩 후 OpenSearch 인덱싱 (백그라운드)."""
    try:
        await index_single_book(book)
        logger.info("[aladin-supplement] OpenSearch 인덱싱 완료: '%s'", book.title)
    except Exception:
        logger.warning("[aladin-supplement] OpenSearch 인덱싱 실패: '%s'", book.title)


async def supplement_with_aladin(
    db: AsyncSession,
    candidates: list[dict],
    genre_keywords: list[str],
    exclude_book_ids: list[str],
    limit: int,
    exclude_isbns: set[str] | None = None,
) -> list[dict]:
    """알라딘 API로 추천 후보 보완.

    부족한 수만큼 알라딘 검색 → DB 저장 → candidates에 합산.
    ISBN 기반으로 서재/dismissed 책 제외.

    Args:
        db: 비동기 DB 세션
        candidates: 기존 OpenSearch 후보 리스트
        genre_keywords: 알라딘 검색 키워드 (선호 장르)
        exclude_book_ids: 제외할 book_id 목록
        limit: 목표 후보 수
        exclude_isbns: 제외할 ISBN 목록 (서재 + dismissed)

    Returns:
        알라딘 보완 후 candidates
    """
    needed = limit - len(candidates)
    if needed <= 0:
        return candidates

    logger.info(
        "[aladin-supplement] 보완 시작: 현재 %d / 목표 %d (필요 %d권)",
        len(candidates), limit, needed,
    )

    existing_ids = {c["book_id"] for c in candidates} | set(exclude_book_ids)
    existing_isbns = {c.get("isbn", "") for c in candidates if c.get("isbn")}
    isbn_exclude = (exclude_isbns or set()) | existing_isbns

    query = " ".join(genre_keywords[:2]) if genre_keywords else "소설 베스트셀러"

    try:
        aladin_results = await aladin_search(query, max_results=needed * 3)
    except Exception:
        logger.warning("[aladin-supplement] 알라딘 API 호출 실패, 보완 건너뜀")
        return candidates

    supplemented = list(candidates)
    for item in aladin_results:
        if len(supplemented) >= limit:
            break

        # ISBN 기반 중복 검사 (서재/dismissed/기존 후보)
        if item.isbn and item.isbn in isbn_exclude:
            continue

        book = await _save_new_book(db, item)
        if book is None:
            continue

        book_id_str = str(book.id)
        if book_id_str in existing_ids:
            continue

        existing_ids.add(book_id_str)
        if book.isbn:
            isbn_exclude.add(book.isbn)

        supplemented.append({
            "book_id": book_id_str,
            "title": book.title,
            "author": book.author or "",
            "genre": book.genre or "",
            "description": book.description or "",
            "isbn": book.isbn or "",
            "cover_image_url": book.cover_image_url or "",
            "score": 0.5,
        })

    logger.info(
        "[aladin-supplement] 보완 완료: %d → %d권",
        len(candidates), len(supplemented),
    )
    return supplemented
