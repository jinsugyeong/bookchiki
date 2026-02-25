"""user_book_indexer: user_books 평점/메모 → OpenSearch user_books 인덱스 임베딩/upsert.

취향 벡터 계산에 필요한 데이터:
- book_embedding: books 인덱스에서 조회 (이미 임베딩됨)
- memo_embedding: 유저 메모를 새로 임베딩 (메모가 있을 때만)
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user_book import UserBook
from app.models.book import Book
from app.opensearch.client import os_client
from app.opensearch.index import USER_BOOKS_INDEX, BOOKS_INDEX
from app.services.rag import embed_text

logger = logging.getLogger(__name__)


def _make_user_book_id(user_id: uuid.UUID, book_id: uuid.UUID) -> str:
    """user_books 인덱스 문서 ID 생성: {user_id}_{book_id}."""
    return f"{user_id}_{book_id}"


def _get_book_embedding_from_index(book_id: uuid.UUID) -> list[float] | None:
    """books 인덱스에서 책 임베딩 조회."""
    try:
        doc = os_client.get(index=BOOKS_INDEX, id=str(book_id))
        return doc["_source"].get("embedding")
    except Exception:
        return None


async def index_user_book(user_book: UserBook, book: Book) -> None:
    """단일 UserBook을 user_books 인덱스에 upsert.

    - book_embedding: books 인덱스에서 조회
    - memo_embedding: 메모가 변경됐을 때만 새로 생성 (OpenAI API 비용 절감)
    """
    doc_id = _make_user_book_id(user_book.user_id, user_book.book_id)
    current_memo = user_book.memo or ""

    # books 인덱스에서 책 임베딩 조회
    book_embedding = _get_book_embedding_from_index(user_book.book_id)
    if book_embedding is None:
        logger.warning(
            "[user-book-indexer] book_embedding not found for book_id=%s, skipping",
            user_book.book_id,
        )
        return

    doc = {
        "user_book_id": doc_id,
        "user_id": str(user_book.user_id),
        "book_id": str(user_book.book_id),
        "book_title": book.title,
        "rating": user_book.rating,
        "status": user_book.status,
        "memo_text": current_memo,
        "book_embedding": book_embedding,
    }

    # 기존 문서의 memo_text와 비교해서 변경됐을 때만 재임베딩
    existing_memo_embedding = None
    try:
        existing_doc = os_client.get(index=USER_BOOKS_INDEX, id=doc_id)
        existing_memo = existing_doc["_source"].get("memo_text", "")
        if existing_memo == current_memo:
            existing_memo_embedding = existing_doc["_source"].get("memo_embedding")
        # memo 변경됐으면 existing_memo_embedding=None → 아래에서 재생성
    except Exception:
        pass  # 문서 없음 → 새로 인덱싱

    if current_memo.strip():
        if existing_memo_embedding is not None:
            # 메모 동일 → 기존 임베딩 재사용
            doc["memo_embedding"] = existing_memo_embedding
        else:
            # 메모 신규/변경 → 새로 임베딩
            memo_embedding, tokens = await embed_text(current_memo)
            doc["memo_embedding"] = memo_embedding
            logger.info(
                "[user-book-indexer] Generated memo_embedding for user_book %s (tokens=%d)",
                doc_id,
                tokens,
            )

    os_client.index(
        index=USER_BOOKS_INDEX,
        id=doc_id,
        body=doc,
    )
    logger.info(
        "[user-book-indexer] Indexed user_book '%s' (user=%s, book=%s)",
        doc_id,
        user_book.user_id,
        book.title,
    )


async def index_all_user_books(db: AsyncSession) -> dict:
    """DB의 모든 user_books를 user_books 인덱스에 임베딩/upsert.

    Returns:
        {"indexed": int, "failed": int, "skipped": int, "total_tokens": int}
    """
    result = await db.execute(
        select(UserBook, Book).join(Book, UserBook.book_id == Book.id)
    )
    rows = result.all()

    indexed = 0
    failed = 0
    skipped = 0
    total_tokens = 0
    # 동일 book_id는 여러 유저가 공유하므로 로컬 캐시로 N+1 조회 방지
    embedding_cache: dict[str, list[float] | None] = {}

    for user_book, book in rows:
        doc_id = _make_user_book_id(user_book.user_id, user_book.book_id)
        try:
            # 기존 문서의 memo_text와 비교해서 변경 없으면 스킵 (OpenAI API 비용 절감)
            current_memo = user_book.memo or ""
            try:
                existing_doc = os_client.get(index=USER_BOOKS_INDEX, id=doc_id)
                existing_memo = existing_doc["_source"].get("memo_text", "")
                if existing_memo == current_memo:
                    skipped += 1
                    continue
            except Exception:
                pass  # 문서 없음 → 새로 인덱싱

            bid = str(user_book.book_id)
            if bid not in embedding_cache:
                embedding_cache[bid] = _get_book_embedding_from_index(user_book.book_id)
            book_embedding = embedding_cache[bid]
            if book_embedding is None:
                skipped += 1
                logger.warning(
                    "[user-book-indexer] book_embedding not found for book_id=%s, skipping",
                    user_book.book_id,
                )
                continue

            doc = {
                "user_book_id": doc_id,
                "user_id": str(user_book.user_id),
                "book_id": str(user_book.book_id),
                "book_title": book.title,
                "rating": user_book.rating,
                "status": user_book.status,
                "memo_text": current_memo,
                "book_embedding": book_embedding,
            }

            if user_book.memo and user_book.memo.strip():
                memo_embedding, tokens = await embed_text(user_book.memo)
                doc["memo_embedding"] = memo_embedding
                total_tokens += tokens

            os_client.index(
                index=USER_BOOKS_INDEX,
                id=doc_id,
                body=doc,
            )
            indexed += 1
            logger.info(
                "[user-book-indexer] Indexed '%s' (%d/%d, skipped=%d)",
                doc_id,
                indexed,
                len(rows),
                skipped,
            )
        except Exception as e:
            failed += 1
            logger.error(
                "[user-book-indexer] Failed to index user_book %s: %s",
                doc_id,
                e,
            )

    logger.info(
        "[user-book-indexer] Done: indexed=%d, failed=%d, skipped=%d, total_tokens=%d",
        indexed,
        failed,
        skipped,
        total_tokens,
    )
    return {
        "indexed": indexed,
        "failed": failed,
        "skipped": skipped,
        "total_tokens": total_tokens,
    }


def delete_user_book(user_id: uuid.UUID, book_id: uuid.UUID) -> None:
    """user_books 인덱스에서 단일 user_book 문서 삭제."""
    doc_id = _make_user_book_id(user_id, book_id)
    try:
        os_client.delete(index=USER_BOOKS_INDEX, id=doc_id, ignore=[404])
        logger.info("[user-book-indexer] Deleted user_book %s from index", doc_id)
    except Exception as e:
        logger.error("[user-book-indexer] Failed to delete user_book %s: %s", doc_id, e)


async def get_user_book_interactions(user_id: uuid.UUID) -> list[dict]:
    """user_books 인덱스에서 특정 유저의 모든 상호작용 데이터 조회.

    취향 벡터 계산용 단일 쿼리.
    Returns:
        [{"book_id": str, "rating": int|None, "book_embedding": list[float],
          "memo_embedding": list[float]|None}]
    """
    body = {
        "size": 1000,
        "query": {
            "term": {"user_id": str(user_id)}
        },
        "_source": ["book_id", "rating", "book_embedding", "memo_embedding"],
    }

    try:
        response = os_client.search(index=USER_BOOKS_INDEX, body=body)
    except Exception as e:
        logger.error(
            "[user-book-indexer] Failed to query interactions for user %s: %s",
            user_id,
            e,
        )
        return []

    hits = response.get("hits", {}).get("hits", [])
    interactions = []
    for hit in hits:
        src = hit["_source"]
        interactions.append({
            "book_id": src.get("book_id"),
            "rating": src.get("rating"),
            "book_embedding": src.get("book_embedding"),
            "memo_embedding": src.get("memo_embedding"),
        })

    logger.info(
        "[user-book-indexer] Fetched %d interactions for user %s",
        len(interactions),
        user_id,
    )
    return interactions
