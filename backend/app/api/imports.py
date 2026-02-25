import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.book_import import ImportResult
from app.services.book_import import import_csv
from app.services.profile_cache import mark_profile_dirty
from app.services.book_indexer import index_single_book
from app.services.user_book_indexer import index_user_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/csv", response_model=ImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import books from a CSV file (북적북적 format supported)."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are supported")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 10MB)")

    try:
        result, created_pairs, new_books = await import_csv(content, current_user.id, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to parse CSV: {e}")

    # CSV 임포트 후 추천 캐시 dirty 마킹
    await mark_profile_dirty(db, current_user.id, reason="csv_imported")

    # 신규 생성된 books를 books 인덱스에 먼저 인덱싱 (user_books 인덱싱 전에 book_embedding 필요)
    for book in new_books:
        try:
            await index_single_book(book)
        except Exception:
            logger.warning("[imports] Failed to index book '%s', skipping", book.title)

    # 신규 생성된 user_books를 user_books 인덱스에 인덱싱
    for user_book, book in created_pairs:
        try:
            await index_user_book(user_book, book)
        except Exception:
            logger.warning("[imports] Failed to index user_book '%s', skipping", book.title)

    return result
