import csv
import io
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user_book import UserBook
from app.models.book_import import BookImport
from app.schemas.book_import import ImportResult

# 북적북적 CSV column mappings
BOOKJUK_COLUMNS = {
    "제목": "title",
    "저자": "author",
    "ISBN": "isbn",
    "isbn": "isbn",
    "ISBN13": "isbn",
    "출판사": "publisher",
    "설명": "description",
    "장르": "genre",
    "표지": "cover_image_url",
    "출간일": "published_at",
    "상태": "status",
    "평점": "rating",
    "메모": "memo",
}

STATUS_MAP = {
    "읽는 중": "reading",
    "읽음": "read",
    "읽고 싶은": "wishlist",
    "reading": "reading",
    "read": "read",
    "wishlist": "wishlist",
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
            db.add(book)
            await db.flush()

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
