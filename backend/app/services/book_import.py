import csv
import io
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user_book import UserBook
from app.models.book_import import BookImport
from app.schemas.book_import import ImportResult
from app.services.aladin import search_books as aladin_search
from app.services.rag import index_book

logger = logging.getLogger(__name__)


import re


def _clean_title_for_search(title: str) -> str:
    """Clean title for better Aladin search results.

    - Remove subtitle after ' - ', ' : ', etc.
    - Keep volume/series numbers (e.g. "환상서점 2")
    - Normalize multiple spaces
    """
    # Remove subtitle (after - or : with spaces)
    title = re.split(r'\s[-:–—]\s', title)[0]
    # Normalize whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    return title


async def _enrich_from_aladin(book: Book) -> None:
    """Search Aladin by title+author and fill in missing fields."""
    clean_title = _clean_title_for_search(book.title)
    author = book.author if book.author and book.author != "Unknown" else ""

    # Try: clean title + author -> clean title only -> original title
    search_queries = [f"{clean_title} {author}".strip()]
    if author:
        search_queries.append(clean_title)
    if clean_title != book.title:
        search_queries.append(book.title)

    results = []
    for query in search_queries:
        try:
            results = await aladin_search(query, max_results=3)
        except Exception:
            logger.warning("Aladin search failed for query '%s'", query)
            continue
        if results:
            logger.info("[enrich] Found '%s' with query '%s'", book.title, query)
            break

    if not results:
        logger.warning("[enrich] No Aladin results for '%s'", book.title)
        return

    # Pick best match (first result, or ISBN match if available)
    match = results[0]
    for r in results:
        if r.isbn and book.isbn and r.isbn == book.isbn:
            match = r
            break

    # Fill only empty fields
    if not book.isbn and match.isbn:
        book.isbn = match.isbn
    if not book.description and match.description:
        book.description = match.description
    if not book.cover_image_url and match.cover_image_url:
        book.cover_image_url = match.cover_image_url
    if not book.genre and match.genre:
        book.genre = match.genre
    if not book.published_at and match.published_at:
        book.published_at = match.published_at
    if (not book.author or book.author == "Unknown") and match.author:
        book.author = match.author

    logger.info("[enrich] '%s' -> isbn=%s, genre=%s, cover=%s",
                book.title, book.isbn, book.genre, bool(book.cover_image_url))

# 북적북적 CSV column mappings
BOOKJUK_COLUMNS = {
    # 북적북적 기본 컬럼: 인덱스,제목,저자,출판사,독서상태,생성일,시작일,읽은 날짜,중단일,평점
    "제목": "title",
    "저자": "author",
    "출판사": "publisher",
    "독서상태": "status",
    "생성일": "created_date",
    "시작일": "started_at",
    "읽은 날짜": "finished_at",
    "중단일": "stopped_at",
    "평점": "rating",
    # 추가 매핑 (다른 CSV 형식 호환)
    "ISBN": "isbn",
    "isbn": "isbn",
    "ISBN13": "isbn",
    "설명": "description",
    "장르": "genre",
    "표지": "cover_image_url",
    "출간일": "published_at",
    "상태": "status",
    "메모": "memo",
    "완독일": "finished_at",
    "종료일": "finished_at",
    "읽기 시작": "started_at",
}

STATUS_MAP = {
    # 북적북적 상태값
    "읽고 있는 책": "reading",
    "읽은 책": "read",
    "읽고 싶은 책": "wishlist",
    "중단한 책": "stopped",
    # 영문
    "reading": "reading",
    "read": "read",
    "wishlist": "wishlist",
    "stopped": "stopped",
}


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return date.fromisoformat(value) if fmt == "%Y-%m-%d" else date(*map(int, value.replace(".", "-").replace("/", "-").split("-")))
        except (ValueError, TypeError):
            continue
    return None


def _parse_rating(value: str) -> int | None:
    if not value:
        return None
    try:
        r = int(float(value))
        return r if 1 <= r <= 5 else None
    except (ValueError, TypeError):
        return None


async def import_csv(
    file_content: bytes,
    user_id,
    db: AsyncSession,
) -> ImportResult:
    """Parse CSV and import books + user_books records."""
    text = file_content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    total = 0
    created = 0
    skipped = 0
    failed = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        total += 1

        # Map columns
        mapped: dict[str, str] = {}
        for csv_col, val in row.items():
            col_key = csv_col.strip()
            if col_key in BOOKJUK_COLUMNS:
                mapped[BOOKJUK_COLUMNS[col_key]] = (val or "").strip()

        title = mapped.get("title", "")
        author = mapped.get("author", "")
        if not title:
            failed += 1
            errors.append(f"Row {row_num}: missing title")
            continue

        isbn = mapped.get("isbn") or None

        # Check existing book by ISBN
        book = None
        if isbn:
            result = await db.execute(select(Book).where(Book.isbn == isbn))
            book = result.scalar_one_or_none()

        if book is None:
            book = Book(
                title=title,
                author=author or "Unknown",
                isbn=isbn,
                description=mapped.get("description") or None,
                cover_image_url=mapped.get("cover_image_url") or None,
                genre=mapped.get("genre") or None,
                published_at=_parse_date(mapped.get("published_at", "")),
            )

            # Enrich missing fields from Aladin API
            await _enrich_from_aladin(book)

            # After enrichment, check if the enriched ISBN already exists in DB
            if book.isbn and not isbn:  # ISBN came from enrichment, not CSV
                existing_by_isbn = await db.execute(select(Book).where(Book.isbn == book.isbn))
                existing_book = existing_by_isbn.scalar_one_or_none()
                if existing_book:
                    logger.info("[import] ISBN %s from enrichment already exists (book '%s'), reusing",
                                book.isbn, existing_book.title)
                    book = existing_book
                else:
                    db.add(book)
                    await db.flush()
            else:
                db.add(book)
                await db.flush()

            # Index in OpenSearch for recommendations/search
            try:
                await index_book(book)
            except Exception:
                logger.warning("Failed to index imported book '%s' in OpenSearch", title)

        # Check if user already has this book
        existing_ub = await db.execute(
            select(UserBook).where(UserBook.user_id == user_id, UserBook.book_id == book.id)
        )
        if existing_ub.scalar_one_or_none():
            skipped += 1
            continue

        status_raw = mapped.get("status", "")
        book_status = STATUS_MAP.get(status_raw, "wishlist")

        user_book = UserBook(
            user_id=user_id,
            book_id=book.id,
            status=book_status,
            rating=_parse_rating(mapped.get("rating", "")),
            memo=mapped.get("memo") or None,
            started_at=_parse_date(mapped.get("started_at", "")),
            finished_at=_parse_date(mapped.get("finished_at", "")),
            source="import",
        )
        db.add(user_book)
        created += 1

    # Record import history
    import_record = BookImport(
        user_id=user_id,
        source_app="csv",
        imported_count=created,
    )
    db.add(import_record)
    await db.commit()

    return ImportResult(
        total=total,
        created=created,
        skipped=skipped,
        failed=failed,
        errors=errors,
    )
