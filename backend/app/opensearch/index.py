"""OpenSearch 인덱스 관리: rag_knowledge 인덱스 및 하이브리드 검색 파이프라인."""

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
