"""RAG 서비스: 임베딩 생성, rag_knowledge 하이브리드 검색.

books 인덱스 임베딩/검색은 제거됨 (자연어 검색이 ask 엔드포인트로 통합).
"""

import logging

from openai import AsyncOpenAI

from app.core.config import settings
from app.opensearch.client import os_client
from app.opensearch.index import RAG_KNOWLEDGE_INDEX

logger = logging.getLogger(__name__)

_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

MAX_EMBED_CHARS = 1000


async def embed_text(text: str) -> tuple[list[float], int]:
    """텍스트를 임베딩 벡터로 변환. (embedding, token_count) 튜플 반환."""
    text = text[:MAX_EMBED_CHARS]
    response = await _openai_client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    tokens = response.usage.total_tokens
    return response.data[0].embedding, tokens


async def search_knowledge(query: str, k: int = 10) -> list[dict]:
    """rag_knowledge 인덱스에서 하이브리드 검색 (질문 기반 추천용).

    Returns:
        [{"text": ..., "source": ..., "book_title": ..., "score": ...}] 리스트
    """
    query_embedding, _ = await embed_text(query)

    body = {
        "size": k,
        "query": {
            "hybrid": {
                "queries": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["text^2", "book_title^3"],
                        }
                    },
                    {
                        "knn": {
                            "embedding": {
                                "vector": query_embedding,
                                "k": k,
                            }
                        }
                    },
                ],
            }
        },
    }

    try:
        response = os_client.search(
            index=RAG_KNOWLEDGE_INDEX,
            body=body,
            params={"search_pipeline": "hybrid-search-pipeline"},
        )
    except Exception:
        logger.info("[search-knowledge] Hybrid unavailable, falling back to KNN")
        response = os_client.search(
            index=RAG_KNOWLEDGE_INDEX,
            body={
                "size": k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": k,
                        }
                    }
                },
            },
        )

    hits = response.get("hits", {}).get("hits", [])
    return [
        {
            "text": hit["_source"].get("text", ""),
            "source": hit["_source"].get("source", ""),
            "book_title": hit["_source"].get("book_title", ""),
            "score": hit["_score"],
        }
        for hit in hits
    ]
