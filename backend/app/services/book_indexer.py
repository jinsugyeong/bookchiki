"""book_indexer: books DB → OpenSearch books 인덱스 임베딩/upsert."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.book import Book
from app.opensearch.client import os_client
from app.opensearch.index import BOOKS_INDEX
from app.services.rag import embed_text

logger = logging.getLogger(__name__)


def _build_embed_text(book: Book) -> str:
    """책 임베딩용 텍스트 구성 (제목 + 저자 + 장르 + 설명)."""
    parts = [book.title, book.author]
    if book.genre:
        parts.append(book.genre)
    if book.description:
        parts.append(book.description[:500])
    return " ".join(parts)


async def index_single_book(book: Book) -> None:
    """단일 Book 레코드를 books 인덱스에 임베딩 후 upsert.

    책 제목+저자+장르+설명을 합쳐 임베딩하고 OpenSearch에 저장.
    """
    embed_input = _build_embed_text(book)
    embedding, tokens = await embed_text(embed_input)

    doc = {
        "book_id": str(book.id),
        "title": book.title,
        "author": book.author,
        "genre": book.genre or "",
        "description": book.description or "",
        "isbn": book.isbn or "",
        "cover_image_url": book.cover_image_url or "",
        "embedding": embedding,
    }

    os_client.index(
        index=BOOKS_INDEX,
        id=str(book.id),
        body=doc,
    )
    logger.info(
        "[book-indexer] Indexed book '%s' (id=%s, tokens=%d)",
        book.title,
        book.id,
        tokens,
    )


async def index_all_books(db: AsyncSession) -> dict:
    """DB의 모든 books를 books 인덱스에 임베딩/upsert.

    Returns:
        {"indexed": int, "failed": int, "total_tokens": int}
    """
    result = await db.execute(select(Book))
    books = result.scalars().all()

    indexed = 0
    failed = 0
    total_tokens = 0

    for book in books:
        try:
            embed_input = _build_embed_text(book)
            embedding, tokens = await embed_text(embed_input)
            total_tokens += tokens

            doc = {
                "book_id": str(book.id),
                "title": book.title,
                "author": book.author,
                "genre": book.genre or "",
                "description": book.description or "",
                "isbn": book.isbn or "",
                "cover_image_url": book.cover_image_url or "",
                "embedding": embedding,
            }

            os_client.index(
                index=BOOKS_INDEX,
                id=str(book.id),
                body=doc,
            )
            indexed += 1
            logger.info(
                "[book-indexer] Indexed '%s' (%d/%d)",
                book.title,
                indexed,
                len(books),
            )
        except Exception as e:
            failed += 1
            logger.error(
                "[book-indexer] Failed to index book '%s': %s",
                book.title,
                e,
            )

    logger.info(
        "[book-indexer] Done: indexed=%d, failed=%d, total_tokens=%d",
        indexed,
        failed,
        total_tokens,
    )
    return {"indexed": indexed, "failed": failed, "total_tokens": total_tokens}


def delete_book_from_index(book_id: uuid.UUID) -> None:
    """books 인덱스에서 단일 book 문서 삭제."""
    try:
        os_client.delete(index=BOOKS_INDEX, id=str(book_id), ignore=[404])
        logger.info("[book-indexer] Deleted book %s from index", book_id)
    except Exception as e:
        logger.error("[book-indexer] Failed to delete book %s: %s", book_id, e)
