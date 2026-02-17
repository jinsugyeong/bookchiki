from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.book import Book
from app.schemas.book import BookCreate, BookResponse, BookSearchResult
from app.services.aladin import search_books as aladin_search
from app.services.rag import index_book

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookResponse])
async def list_books(
    q: str | None = Query(None, description="Search by title or author"),
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List books with optional search."""
    query = select(Book)
    if q:
        query = query.where(Book.title.ilike(f"%{q}%") | Book.author.ilike(f"%{q}%"))
    query = query.order_by(Book.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/search/aladin", response_model=list[BookSearchResult])
async def search_aladin(
    q: str = Query(..., description="Search query for Aladin API"),
    max_results: int = Query(20, ge=1, le=50),
):
    """Search books via Aladin API."""
    return await aladin_search(q, max_results=max_results)


@router.post("/search/aladin/select", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def select_aladin_book(
    book_data: BookSearchResult,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a selected Aladin search result to the books table."""
    if book_data.isbn:
        existing = await db.execute(select(Book).where(Book.isbn == book_data.isbn))
        found = existing.scalar_one_or_none()
        if found:
            return found

    book = Book(
        title=(book_data.title or "")[:500],
        author=(book_data.author or "")[:1000],
        isbn=book_data.isbn,
        description=book_data.description,
        cover_image_url=(book_data.cover_image_url or "")[:500],
        genre=(book_data.genre or "")[:500],
        published_at=book_data.published_at,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)

    # Index in OpenSearch (background, don't fail the request)
    try:
        await index_book(book)
    except Exception:
        pass

    return book


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single book by ID."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    book_in: BookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new book entry."""
    # Check for duplicate ISBN
    if book_in.isbn:
        existing = await db.execute(select(Book).where(Book.isbn == book_in.isbn))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Book with this ISBN already exists")

    book = Book(**book_in.model_dump())
    db.add(book)
    await db.commit()
    await db.refresh(book)

    try:
        await index_book(book)
    except Exception:
        pass

    return book
