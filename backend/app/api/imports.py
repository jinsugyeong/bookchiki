from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.book_import import ImportResult
from app.services.book_import import import_csv
from app.services.profile_cache import mark_profile_dirty

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
        result = await import_csv(content, current_user.id, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to parse CSV: {e}")

    # CSV 임포트 후 추천 캐시 dirty 마킹
    await mark_profile_dirty(db, current_user.id, reason="csv_imported")

    return result
