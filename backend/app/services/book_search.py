"""book_search: books 인덱스 하이브리드 검색 (BM25 + k-NN).

취향 벡터가 있으면 하이브리드 검색, 없으면 cold start 폴백.
모든 검색에서 book_id + ISBN 이중 exclude 적용.
"""

import logging

from app.opensearch.client import os_client
from app.opensearch.index import BOOKS_INDEX, HYBRID_PIPELINE_NAME

logger = logging.getLogger(__name__)


def _should_exclude(
    book_id: str,
    isbn: str,
    exclude_ids: set[str],
    exclude_isbns: set[str],
) -> bool:
    """book_id 또는 ISBN으로 제외 대상인지 판별."""
    if book_id in exclude_ids:
        return True
    if isbn and isbn in exclude_isbns:
        return True
    return False


def _hit_to_dict(hit: dict) -> dict:
    """OpenSearch hit를 표준 dict로 변환."""
    src = hit["_source"]
    return {
        "book_id": src.get("book_id", ""),
        "title": src.get("title", ""),
        "author": src.get("author", ""),
        "genre": src.get("genre", ""),
        "description": src.get("description", ""),
        "isbn": src.get("isbn", ""),
        "cover_image_url": src.get("cover_image_url", ""),
        "score": hit.get("_score", 0.0),
    }


async def search_books_hybrid(
    preference_vector: list[float],
    genre_keywords: list[str],
    exclude_book_ids: list[str],
    k: int = 10,
    author_keywords: list[str] | None = None,
    exclude_isbns: set[str] | None = None,
) -> list[dict]:
    """books 인덱스에서 하이브리드 검색 (BM25 + k-NN).

    book_id + ISBN 이중 exclude로 서재/dismissed 책 제외.
    """
    id_set = set(exclude_book_ids)
    isbn_set = exclude_isbns or set()
    fetch_size = len(id_set) + k * 3

    # BM25 쿼리: 장르 + 작가 키워드
    should_clauses = []
    if genre_keywords:
        should_clauses += [
            {"terms": {"genre": genre_keywords, "boost": 1.5}},
            {
                "multi_match": {
                    "query": " ".join(genre_keywords),
                    "fields": ["description", "title"],
                    "type": "best_fields",
                }
            },
        ]
    if author_keywords:
        should_clauses.append(
            {
                "multi_match": {
                    "query": " ".join(author_keywords),
                    "fields": ["author"],
                    "type": "best_fields",
                    "boost": 1.2,
                }
            }
        )

    genre_query = {"bool": {"should": should_clauses}} if should_clauses else {"match_all": {}}

    knn_query = {
        "knn": {
            "embedding": {
                "vector": preference_vector,
                "k": fetch_size,
            }
        }
    }

    body = {
        "size": fetch_size,
        "query": {"hybrid": {"queries": [genre_query, knn_query]}},
        "_source": ["book_id", "title", "author", "genre", "description", "isbn", "cover_image_url"],
    }

    try:
        response = os_client.search(
            index=BOOKS_INDEX,
            body=body,
            params={"search_pipeline": HYBRID_PIPELINE_NAME},
        )
    except Exception:
        logger.warning("[book-search] Hybrid search failed, falling back to k-NN only", exc_info=True)
        response = os_client.search(
            index=BOOKS_INDEX,
            body={
                "size": fetch_size,
                "query": knn_query,
                "_source": ["book_id", "title", "author", "genre", "description", "isbn", "cover_image_url"],
            },
        )

    hits = response.get("hits", {}).get("hits", [])

    results = []
    for hit in hits:
        d = _hit_to_dict(hit)
        if _should_exclude(d["book_id"], d["isbn"], id_set, isbn_set):
            continue
        results.append(d)
        if len(results) >= k:
            break

    logger.info(
        "[book-search] Hybrid: %d results (k=%d, genres=%s, excluded_ids=%d, excluded_isbns=%d)",
        len(results), k, genre_keywords[:3], len(id_set), len(isbn_set),
    )
    return results


async def search_books_cold_start(
    k: int = 10,
    exclude_book_ids: list[str] | None = None,
    exclude_isbns: set[str] | None = None,
) -> list[dict]:
    """preference_vector 없을 때 폴백 검색.

    설명 + 임베딩이 있는 책 중 서재/dismissed 제외 후 상위 k개 반환.
    """
    id_set = set(exclude_book_ids or [])
    isbn_set = exclude_isbns or set()
    fetch_size = len(id_set) + k * 3

    body = {
        "size": fetch_size,
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "description"}},
                    {"exists": {"field": "embedding"}},
                ],
            }
        },
        "_source": ["book_id", "title", "author", "genre", "description", "isbn", "cover_image_url"],
    }

    try:
        response = os_client.search(index=BOOKS_INDEX, body=body)
    except Exception:
        logger.error("[book-search] Cold start search failed")
        return []

    hits = response.get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        d = _hit_to_dict(hit)
        if _should_exclude(d["book_id"], d["isbn"], id_set, isbn_set):
            continue
        results.append(d)
        if len(results) >= k:
            break

    logger.info(
        "[book-search] Cold start: %d results (excluded_ids=%d, excluded_isbns=%d)",
        len(results), len(id_set), len(isbn_set),
    )
    return results
