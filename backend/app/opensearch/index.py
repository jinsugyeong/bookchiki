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


def ensure_index() -> None:
    if os_client.indices.exists(index=INDEX_NAME):
        logger.info("OpenSearch index '%s' already exists", INDEX_NAME)
        return
    os_client.indices.create(index=INDEX_NAME, body=BOOKS_MAPPING)
    logger.info("Created OpenSearch index '%s'", INDEX_NAME)
