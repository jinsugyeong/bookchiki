from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.user_book import UserBook
from app.models.highlight import Highlight
from app.schemas.highlight import HighlightCreate, HighlightUpdate, HighlightResponse

router = APIRouter(prefix="/highlights", tags=["highlights"])


async def _verify_user_book(db: AsyncSession, user_book_id: UUID, user_id: UUID) -> UserBook:
    """Verify user_book belongs to current user."""
    result = await db.execute(
        select(UserBook).where(UserBook.id == user_book_id, UserBook.user_id == user_id)
    )
    user_book = result.scalar_one_or_none()
    if user_book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found in your library")
    return user_book


@router.get("", response_model=list[HighlightResponse])
async def list_highlights(
    user_book_id: UUID | None = Query(None, description="Filter by user_book ID"),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's highlights, optionally filtered by user_book."""
    query = (
        select(Highlight)
        .join(UserBook)
        .where(UserBook.user_id == current_user.id)
    )
    if user_book_id:
        query = query.where(Highlight.user_book_id == user_book_id)
    query = query.order_by(Highlight.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=HighlightResponse, status_code=status.HTTP_201_CREATED)
async def create_highlight(
    highlight_in: HighlightCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new highlight."""
    await _verify_user_book(db, highlight_in.user_book_id, current_user.id)
    highlight = Highlight(**highlight_in.model_dump())
    db.add(highlight)
    await db.commit()
    await db.refresh(highlight)
    return highlight


@router.patch("/{highlight_id}", response_model=HighlightResponse)
async def update_highlight(
    highlight_id: UUID,
    update: HighlightUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a highlight."""
    result = await db.execute(
        select(Highlight).join(UserBook).where(
            Highlight.id == highlight_id, UserBook.user_id == current_user.id
        )
    )
    highlight = result.scalar_one_or_none()
    if highlight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(highlight, field, value)

    await db.commit()
    await db.refresh(highlight)
    return highlight


@router.delete("/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a highlight."""
    result = await db.execute(
        select(Highlight).join(UserBook).where(
            Highlight.id == highlight_id, UserBook.user_id == current_user.id
        )
    )
    highlight = result.scalar_one_or_none()
    if highlight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

    await db.delete(highlight)
    await db.commit()
