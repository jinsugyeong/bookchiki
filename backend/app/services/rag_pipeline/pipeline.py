"""
RAG 파이프라인: 커뮤니티 데이터 파싱 → 배치 임베딩 → rag_knowledge 적재.

사용법:
    pipeline = RagPipeline(data_dir=Path("/app/output"))
    result = await pipeline.run()
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.opensearch.client import os_client
from app.opensearch.index import RAG_KNOWLEDGE_INDEX
from app.services.rag_pipeline.parsers.recommend_parser import RecommendParser
from app.services.rag_pipeline.parsers.book_reviews_parser import BookReviewsParser
from app.services.rag_pipeline.parsers.thread_reviews_parser import ThreadReviewsParser
from app.services.rag_pipeline.parsers.base_parser import Chunk

logger = logging.getLogger(__name__)

# 배치당 임베딩 요청 수 (OpenAI rate limit 고려)
BATCH_SIZE = 50
# 청크 텍스트 최대 길이 (임베딩용)
MAX_EMBED_CHARS = 500

# 소스별 파일명 매핑 (monthly_closing은 시딩 전용 → RAG 인덱싱 제외)
SOURCE_FILES = {
    "recommend": "recommend.md",
    "reviews": "book_reviews.json",
    "thread_reviews": "thread_review.json",
}


@dataclass
class PipelineResult:
    """파이프라인 실행 결과."""
    total: int = 0
    indexed: int = 0
    skipped: int = 0
    errors: int = 0
    source_stats: dict = field(default_factory=dict)


def _generate_chunk_id(source: str, text: str) -> str:
    """source + text 기반 SHA256 해시로 chunk_id 생성 (멱등 보장)."""
    content = f"{source}:{text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class RagPipeline:
    """커뮤니티 데이터를 파싱하여 rag_knowledge 인덱스에 적재하는 파이프라인."""

    def __init__(self, data_dir: Path = Path("/app/output")):
        """파이프라인 초기화.

        Args:
            data_dir: 커뮤니티 데이터 파일들이 위치한 디렉토리
        """
        self.data_dir = data_dir
        # monthly_closing은 books 시딩 전용 (community_seeder.py에서 사용)
        self.parsers = {
            "recommend": RecommendParser(),
            "reviews": BookReviewsParser(),
            "thread_reviews": ThreadReviewsParser(),
        }
        self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def run(self, sources: Optional[List[str]] = None) -> PipelineResult:
        """파이프라인 실행.

        Args:
            sources: 처리할 소스 목록 (None이면 전체 소스 처리)

        Returns:
            PipelineResult (total, indexed, skipped, errors)
        """
        result = PipelineResult()
        target_sources = sources or list(self.parsers.keys())

        all_chunks: List[Chunk] = []

        # 1단계: 파서별 청크 파싱
        for source_name in target_sources:
            parser = self.parsers.get(source_name)
            file_name = SOURCE_FILES.get(source_name)

            if not parser or not file_name:
                logger.warning("[pipeline] Unknown source: %s", source_name)
                continue

            file_path = self.data_dir / file_name
            if not file_path.exists():
                logger.warning("[pipeline] File not found: %s", file_path)
                result.source_stats[source_name] = {"chunks": 0, "error": "file_not_found"}
                continue

            try:
                chunks = parser.parse(str(file_path))
                # chunk_id가 없는 청크에 SHA256 hash 할당
                for chunk in chunks:
                    if not chunk.chunk_id:
                        chunk.chunk_id = _generate_chunk_id(chunk.source, chunk.text)
                all_chunks.extend(chunks)
                result.source_stats[source_name] = {"chunks": len(chunks)}
                logger.info("[pipeline] %s: parsed %d chunks", source_name, len(chunks))
            except Exception as e:
                logger.exception("[pipeline] Failed to parse source '%s': %s", source_name, e)
                result.source_stats[source_name] = {"chunks": 0, "error": str(e)}
                result.errors += 1

        result.total = len(all_chunks)
        logger.info("[pipeline] Total chunks to embed: %d", result.total)

        if not all_chunks:
            return result

        # 2단계: 배치 임베딩 + OpenSearch 적재
        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[i : i + BATCH_SIZE]
            batch_texts = [chunk.text[:MAX_EMBED_CHARS] for chunk in batch]

            try:
                embeddings = await self._embed_batch(batch_texts)
            except Exception as e:
                logger.error("[pipeline] Embedding batch %d failed: %s", i // BATCH_SIZE, e)
                result.errors += len(batch)
                continue

            # OpenSearch bulk 적재
            bulk_actions = []
            for chunk, embedding in zip(batch, embeddings):
                doc = {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "source": chunk.source,
                    "book_title": chunk.metadata.get("book_title", ""),
                    "category": chunk.metadata.get("category", ""),
                    "author": chunk.metadata.get("author", ""),
                    "embedding": embedding,
                }
                bulk_actions.append({
                    "_index": RAG_KNOWLEDGE_INDEX,
                    "_id": chunk.chunk_id,
                    "_source": doc,
                })

            indexed, errors = self._bulk_index(bulk_actions)
            result.indexed += indexed
            result.errors += errors

            logger.info(
                "[pipeline] Batch %d/%d: indexed=%d errors=%d",
                i // BATCH_SIZE + 1,
                (len(all_chunks) + BATCH_SIZE - 1) // BATCH_SIZE,
                indexed,
                errors,
            )

        result.skipped = result.total - result.indexed - result.errors
        logger.info(
            "[pipeline] Done: total=%d indexed=%d skipped=%d errors=%d",
            result.total, result.indexed, result.skipped, result.errors,
        )
        return result

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """텍스트 목록을 배치로 임베딩 생성.

        OpenAI API는 단일 호출에 list[str] 지원 → N+1 방지.
        """
        response = await self._openai_client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=texts,
        )
        # 응답 순서 보장 (index 기반 정렬)
        sorted_data = sorted(response.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]

    def _bulk_index(self, actions: List[dict]) -> tuple[int, int]:
        """OpenSearch helpers.bulk() 스타일 일괄 인덱싱.

        Returns:
            (indexed_count, error_count) 튜플
        """
        if not actions:
            return 0, 0

        # OpenSearch Python SDK의 bulk API 사용
        try:
            from opensearchpy import helpers as os_helpers
            success, failed = os_helpers.bulk(
                os_client,
                actions,
                raise_on_error=False,
                stats_only=True,
            )
            return success, failed
        except ImportError:
            # helpers 미사용 시 개별 index로 폴백
            indexed = 0
            errors = 0
            for action in actions:
                try:
                    os_client.index(
                        index=action["_index"],
                        id=action["_id"],
                        body=action["_source"],
                    )
                    indexed += 1
                except Exception as e:
                    logger.warning("[pipeline] Failed to index chunk %s: %s", action["_id"], e)
                    errors += 1
            return indexed, errors
        except Exception as e:
            logger.error("[pipeline] Bulk index failed: %s", e)
            return 0, len(actions)
