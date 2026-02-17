import logging

from app.opensearch.client import os_client

logger = logging.getLogger(__name__)

INDEX_NAME = "books"

BOOKS_MAPPING = {
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
                "fields": {"keyword": {"type": "keyword"}},
            },
            "description": {"type": "text", "analyzer": "nori"},
            "genre": {"type": "keyword"},
            "isbn": {"type": "keyword"},
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


def ensure_index() -> None:
    """OpenSearch 인덱스 및 하이브리드 검색 파이프라인 자동 생성."""
    if os_client.indices.exists(index=INDEX_NAME):
        logger.info("OpenSearch index '%s' already exists", INDEX_NAME)
    else:
        os_client.indices.create(index=INDEX_NAME, body=BOOKS_MAPPING)
        logger.info("Created OpenSearch index '%s'", INDEX_NAME)

    # 하이브리드 검색 파이프라인 생성 (이미 존재하면 덮어씀)
    try:
        os_client.http.put(
            f"/_search/pipeline/{HYBRID_PIPELINE_NAME}",
            body=HYBRID_PIPELINE_BODY,
        )
        logger.info("Ensured hybrid search pipeline '%s'", HYBRID_PIPELINE_NAME)
    except Exception:
        logger.warning("Failed to create hybrid search pipeline")
