"""book_search: books 인덱스 하이브리드 검색 (BM25 + k-NN).

취향 벡터가 있으면 하이브리드 검색, 없으면 cold start 폴백.
"""

import logging

from app.opensearch.client import os_client
from app.opensearch.index import BOOKS_INDEX, HYBRID_PIPELINE_NAME

logger = logging.getLogger(__name__)


async def search_books_hybrid(
    preference_vector: list[float],
    genre_keywords: list[str],
    exclude_book_ids: list[str],
    k: int = 10,
) -> list[dict]:
    """books 인덱스에서 하이브리드 검색 (BM25 + k-NN).

    Args:
        preference_vector: 1536차원 취향 벡터
        genre_keywords: BM25 검색용 장르 키워드 목록
        exclude_book_ids: 이미 서재에 있는 book_id 목록 (제외용)
        k: 반환할 최대 결과 수

    Returns:
        [{"book_id", "title", "author", "genre", "description",
          "isbn", "cover_image_url", "score"}] 리스트
    """
    fetch_size = k * 3  # 제외 필터링 후 k개 확보 여유분

    # BM25 쿼리: 장르 키워드를 genre + description 필드에서 검색
    if genre_keywords:
        genre_query = {
            "bool": {
                "should": [
                    {"terms": {"genre": genre_keywords, "boost": 1.5}},
                    {
                        "multi_match": {
                            "query": " ".join(genre_keywords),
                            "fields": ["description", "title"],
                            "type": "best_fields",
                        }
                    },
                ]
            }
        }
    else:
        genre_query = {"match_all": {}}

    # k-NN 쿼리
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
        "query": {
            "hybrid": {
                "queries": [genre_query, knn_query],
            }
        },
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

    exclude_set = set(exclude_book_ids)
    results = []
    for hit in hits:
        src = hit["_source"]
        bid = src.get("book_id", "")
        if bid in exclude_set:
            continue
        results.append({
            "book_id": bid,
            "title": src.get("title", ""),
            "author": src.get("author", ""),
            "genre": src.get("genre", ""),
            "description": src.get("description", ""),
            "isbn": src.get("isbn", ""),
            "cover_image_url": src.get("cover_image_url", ""),
            "score": hit.get("_score", 0.0),
        })
        if len(results) >= k:
            break

    logger.info(
        "[book-search] Hybrid search: %d results (k=%d, genres=%s, excluded=%d)",
        len(results),
        k,
        genre_keywords[:3],
        len(exclude_book_ids),
    )
    return results


async def search_books_cold_start(k: int = 10) -> list[dict]:
    """preference_vector가 없을 때 폴백 검색.

    설명 + 임베딩이 있는 책 중 상위 k개 반환.

    Args:
        k: 반환할 최대 결과 수

    Returns:
        search_books_hybrid과 동일한 형식의 dict 리스트
    """
    body = {
        "size": k,
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
    results = [
        {
            "book_id": hit["_source"].get("book_id", ""),
            "title": hit["_source"].get("title", ""),
            "author": hit["_source"].get("author", ""),
            "genre": hit["_source"].get("genre", ""),
            "description": hit["_source"].get("description", ""),
            "isbn": hit["_source"].get("isbn", ""),
            "cover_image_url": hit["_source"].get("cover_image_url", ""),
            "score": hit.get("_score", 0.0),
        }
        for hit in hits
    ]

    logger.info("[book-search] Cold start: %d results", len(results))
    return results
