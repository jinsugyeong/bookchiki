"""OpenSearch 인덱스 관리: rag_knowledge, books, user_books 인덱스 및 하이브리드 검색 파이프라인."""

import logging

from app.opensearch.client import os_client

logger = logging.getLogger(__name__)

# ── rag_knowledge 인덱스 ──────────────────────────────────────────────────────
RAG_KNOWLEDGE_INDEX = "rag_knowledge"

RAG_KNOWLEDGE_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
        },
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "text": {"type": "text", "analyzer": "nori"},
            "source": {"type": "keyword"},  # recommend / reviews / thread_reviews
            "book_title": {
                "type": "text",
                "analyzer": "nori",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "category": {"type": "keyword"},   # recommend 전용
            "author": {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                },
            },
        }
    },
}

# ── books 인덱스 ──────────────────────────────────────────────────────────────
BOOKS_INDEX = "books"

BOOKS_INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
        },
    },
    "mappings": {
        "properties": {
            "book_id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "nori",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "author": {
                "type": "text",
                "analyzer": "nori",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "genre": {"type": "keyword"},
            "description": {"type": "text", "analyzer": "nori"},
            "isbn": {"type": "keyword"},
            "cover_image_url": {"type": "keyword", "index": False},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                },
            },
        }
    },
}

# ── user_books 인덱스 ─────────────────────────────────────────────────────────
USER_BOOKS_INDEX = "user_books"

USER_BOOKS_INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
        },
    },
    "mappings": {
        "properties": {
            # user_book_id = "{user_id}_{book_id}"
            "user_book_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "book_id": {"type": "keyword"},
            "book_title": {
                "type": "text",
                "analyzer": "nori",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "rating": {"type": "integer"},       # 1~5, null 가능
            "status": {"type": "keyword"},        # reading / read / wishlist
            "memo_text": {"type": "text", "analyzer": "nori"},  # nullable
            # books 인덱스에서 복사한 책 임베딩 (취향 벡터 계산에 사용)
            "book_embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                },
            },
            # 유저 메모 임베딩 (메모가 있을 때만 null이 아님)
            "memo_embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                },
            },
        }
    },
}

# ── 하이브리드 검색 파이프라인 ────────────────────────────────────────────────
HYBRID_PIPELINE_NAME = "hybrid-search-pipeline"
HYBRID_PIPELINE_BODY = {
    "description": "BM25 + KNN 하이브리드 검색 파이프라인",
    "phase_results_processors": [
        {
            "normalization-processor": {
                "normalization": {"technique": "min_max"},
                "combination": {
                    "technique": "arithmetic_mean",
                    "parameters": {"weights": [0.3, 0.7]},
                },
            }
        }
    ],
}


def _ensure_hybrid_pipeline() -> None:
    """하이브리드 검색 파이프라인 생성 (이미 존재하면 덮어씀)."""
    try:
        os_client.http.put(
            f"/_search/pipeline/{HYBRID_PIPELINE_NAME}",
            body=HYBRID_PIPELINE_BODY,
        )
        logger.info("Ensured hybrid search pipeline '%s'", HYBRID_PIPELINE_NAME)
    except Exception:
        logger.warning("Failed to create hybrid search pipeline")


def ensure_knowledge_index() -> None:
    """rag_knowledge OpenSearch 인덱스 및 하이브리드 검색 파이프라인 자동 생성."""
    if os_client.indices.exists(index=RAG_KNOWLEDGE_INDEX):
        logger.info("OpenSearch index '%s' already exists", RAG_KNOWLEDGE_INDEX)
    else:
        os_client.indices.create(index=RAG_KNOWLEDGE_INDEX, body=RAG_KNOWLEDGE_MAPPING)
        logger.info("Created OpenSearch index '%s'", RAG_KNOWLEDGE_INDEX)

    _ensure_hybrid_pipeline()


def ensure_books_index() -> None:
    """books OpenSearch 인덱스 자동 생성."""
    if os_client.indices.exists(index=BOOKS_INDEX):
        logger.info("OpenSearch index '%s' already exists", BOOKS_INDEX)
    else:
        os_client.indices.create(index=BOOKS_INDEX, body=BOOKS_INDEX_MAPPING)
        logger.info("Created OpenSearch index '%s'", BOOKS_INDEX)


def ensure_user_books_index() -> None:
    """user_books OpenSearch 인덱스 자동 생성."""
    if os_client.indices.exists(index=USER_BOOKS_INDEX):
        logger.info("OpenSearch index '%s' already exists", USER_BOOKS_INDEX)
    else:
        os_client.indices.create(index=USER_BOOKS_INDEX, body=USER_BOOKS_INDEX_MAPPING)
        logger.info("Created OpenSearch index '%s'", USER_BOOKS_INDEX)
