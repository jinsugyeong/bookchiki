from uuid import UUID
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.book import Book
from app.models.user_book import UserBook
from app.schemas.user_book import UserBookCreate, UserBookUpdate, UserBookResponse, ReadingStats
from app.services.profile_cache import mark_profile_dirty

router = APIRouter(prefix="/my-books", tags=["my-books"])


@router.get("/stats", response_model=ReadingStats)
async def get_reading_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get reading statistics for current user."""
    result = await db.execute(
        select(UserBook).options(joinedload(UserBook.book)).where(UserBook.user_id == current_user.id)
    )
    user_books = result.unique().scalars().all()

    # Calculate stats
    total = len(user_books)
    read_count = sum(1 for ub in user_books if ub.status == "read")
    reading_count = sum(1 for ub in user_books if ub.status == "reading")
    wishlist_count = sum(1 for ub in user_books if ub.status == "wishlist")

    ratings = [ub.rating for ub in user_books if ub.rating is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else None

    # Genre distribution
    genres = [ub.book.genre for ub in user_books if ub.book and ub.book.genre]
    genre_dist = dict(Counter(genres))

    # Monthly counts (based on finished_at, fallback to created_at)
    monthly = Counter()
    for ub in user_books:
        if ub.status == "read":
            dt = ub.finished_at or ub.created_at
            key = dt.strftime("%Y-%m") if hasattr(dt, 'strftime') else str(dt)[:7]
            monthly[key] += 1

    return ReadingStats(
        total_books=total,
        books_read=read_count,
        books_reading=reading_count,
        books_wishlist=wishlist_count,
        average_rating=round(avg_rating, 1) if avg_rating else None,
        genre_distribution=genre_dist,
        monthly_counts=dict(monthly),
    )


@router.get("", response_model=list[UserBookResponse])
async def list_my_books(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's books with optional status filter."""
    query = select(UserBook).options(joinedload(UserBook.book)).where(UserBook.user_id == current_user.id)
    if status_filter:
        query = query.where(UserBook.status == status_filter)
    query = query.order_by(UserBook.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.unique().scalars().all()


@router.post("", response_model=UserBookResponse, status_code=status.HTTP_201_CREATED)
async def add_book(
    user_book_in: UserBookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a book to current user's library."""
    # Check book exists
    book = await db.execute(select(Book).where(Book.id == user_book_in.book_id))
    if book.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    # Check duplicate
    existing = await db.execute(
        select(UserBook).where(UserBook.user_id == current_user.id, UserBook.book_id == user_book_in.book_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Book already in your library")

    user_book = UserBook(user_id=current_user.id, **user_book_in.model_dump())
    db.add(user_book)
    await db.commit()

    # 추천 캐시 dirty 마킹
    await mark_profile_dirty(db, current_user.id, reason="book_added")

    # Re-fetch with book relationship loaded
    result = await db.execute(
        select(UserBook).options(joinedload(UserBook.book)).where(UserBook.id == user_book.id)
    )
    return result.unique().scalar_one()


@router.patch("/{user_book_id}", response_model=UserBookResponse)
async def update_my_book(
    user_book_id: UUID,
    update: UserBookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update status, rating, or memo for a book in user's library."""
    result = await db.execute(
        select(UserBook).where(UserBook.id == user_book_id, UserBook.user_id == current_user.id)
    )
    user_book = result.scalar_one_or_none()
    if user_book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found in your library")

    update_data = update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user_book, field, value)

    await db.commit()

    # DB 추천 캐시 dirty 마킹
    await mark_profile_dirty(db, current_user.id, reason="book_updated")

    # Re-fetch with book relationship loaded
    result = await db.execute(
        select(UserBook).options(joinedload(UserBook.book)).where(UserBook.id == user_book_id)
    )
    return result.unique().scalar_one()


@router.delete("/{user_book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_my_book(
    user_book_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a book from user's library."""
    result = await db.execute(
        select(UserBook).where(UserBook.id == user_book_id, UserBook.user_id == current_user.id)
    )
    user_book = result.scalar_one_or_none()
    if user_book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found in your library")

    await db.delete(user_book)
    await db.commit()

    # 추천 캐시 dirty 마킹
    await mark_profile_dirty(db, current_user.id, reason="book_deleted")
