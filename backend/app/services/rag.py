"""RAG 서비스: 임베딩 생성, OpenSearch 인덱싱, 하이브리드 검색."""

import logging
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book
from app.opensearch.client import os_client
from app.opensearch.index import INDEX_NAME, ensure_index
from app.services.aladin import search_books as aladin_search

logger = logging.getLogger(__name__)

_index_ensured = False


def _ensure_index_lazy() -> None:
    """OpenSearch 인덱스가 올바른 매핑으로 존재하는지 확인. 없으면 생성."""
    global _index_ensured
    if _index_ensured:
        return
    try:
        if os_client.indices.exists(index=INDEX_NAME):
            # 매핑이 올바른지 확인 (knn_vector 타입)
            mapping = os_client.indices.get_mapping(index=INDEX_NAME)
            props = mapping.get(INDEX_NAME, {}).get("mappings", {}).get("properties", {})
            emb_type = props.get("embedding", {}).get("type", "")
            if emb_type != "knn_vector":
                logger.warning("[rag] Index '%s' has wrong embedding type '%s', recreating",
                               INDEX_NAME, emb_type)
                os_client.indices.delete(index=INDEX_NAME)
                ensure_index()
        else:
            ensure_index()
        _index_ensured = True
    except Exception:
        logger.warning("[rag] OpenSearch index ensure failed, will retry next call")

_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


MAX_EMBED_CHARS = 1000
# text-embedding-3-small: $0.02 / 1M tokens
COST_PER_TOKEN = 0.02 / 1_000_000
MIN_SCORE_THRESHOLD = 0.75  # 최고 점수가 이 이상이면 결과 충분으로 판단
MAX_ALADIN_SEED = 10  # 검색 보완 시 최대 시딩 권수


async def embed_text(text: str) -> tuple[list[float], int]:
    """텍스트를 임베딩 벡터로 변환. (embedding, token_count) 튜플 반환."""
    text = text[:MAX_EMBED_CHARS]
    response = await _openai_client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    tokens = response.usage.total_tokens
    return response.data[0].embedding, tokens


def _build_book_text(book: Book) -> str:
    """임베딩용 책 텍스트 표현 생성."""
    parts = [book.title]
    if book.author:
        parts.append(f"저자: {book.author}")
    if book.genre:
        parts.append(f"장르: {book.genre}")
    if book.description:
        parts.append(book.description)
    return " | ".join(parts)


async def index_book(book: Book) -> None:
    """책의 임베딩을 생성하고 OpenSearch에 인덱싱."""
    _ensure_index_lazy()
    text = _build_book_text(book)
    embedding, tokens = await embed_text(text)
    cost = tokens * COST_PER_TOKEN

    doc = {
        "book_id": str(book.id),
        "title": book.title,
        "author": book.author or "",
        "description": book.description or "",
        "genre": book.genre or "",
        "isbn": book.isbn or "",
        "embedding": embedding,
    }

    os_client.index(index=INDEX_NAME, id=str(book.id), body=doc)
    logger.info(
        "[embedding] book_id=%s tokens=%d cost=$%.6f title='%s'",
        book.id, tokens, cost, book.title,
    )


def _is_indexed(book_id: UUID) -> bool:
    """해당 책이 이미 OpenSearch에 인덱싱되어 있는지 확인."""
    try:
        return os_client.exists(index=INDEX_NAME, id=str(book_id))
    except Exception:
        return False


async def index_all_books(db: AsyncSession) -> int:
    """OpenSearch에 아직 인덱싱되지 않은 책들을 일괄 인덱싱. 새로 인덱싱된 권수 반환."""
    result = await db.execute(select(Book))
    books = result.scalars().all()

    count = 0
    skipped = 0
    for book in books:
        if _is_indexed(book.id):
            skipped += 1
            continue
        try:
            await index_book(book)
            count += 1
        except Exception:
            logger.exception("Failed to index book %s", book.id)

    logger.info("Indexed %d new / %d skipped / %d total books", count, skipped, len(books))
    return count


def count_indexed() -> int:
    """OpenSearch 인덱스의 전체 문서 수 반환."""
    try:
        result = os_client.count(index=INDEX_NAME)
        return result.get("count", 0)
    except Exception:
        logger.warning("Failed to count indexed documents")
        return 0


def _do_opensearch_query(
    query: str,
    query_embedding: list[float],
    limit: int,
) -> list[dict]:
    """OpenSearch 하이브리드 또는 KNN 검색 실행."""
    _ensure_index_lazy()
    body = {
        "size": limit,
        "query": {
            "hybrid": {
                "queries": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "author^2", "description", "genre"],
                        }
                    },
                    {
                        "knn": {
                            "embedding": {
                                "vector": query_embedding,
                                "k": limit,
                            }
                        }
                    },
                ],
            }
        },
    }

    try:
        response = os_client.search(
            index=INDEX_NAME,
            body=body,
            params={"search_pipeline": "hybrid-search-pipeline"},
        )
    except Exception:
        logger.info("Hybrid search unavailable, falling back to KNN-only search")
        response = os_client.search(
            index=INDEX_NAME,
            body={
                "size": limit,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": limit,
                        }
                    }
                },
            },
        )

    hits = response.get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        src = hit["_source"]
        results.append({
            "book_id": src["book_id"],
            "score": hit["_score"],
            "title": src.get("title", ""),
            "author": src.get("author", ""),
            "description": src.get("description", ""),
            "genre": src.get("genre", ""),
        })
    return results


async def _suggest_search_terms_via_llm(query: str) -> list[dict]:
    """LLM이 자연어 쿼리를 분석하여 알라딘 검색에 적합한 검색어 목록 생성.

    작가 이름은 환각 가능성이 낮으므로, 작가 이름 + 장르 키워드를 조합하여 검색.
    반환: [{"search_term": "박준 시집", "type": "author"}, ...] 형태의 리스트.
    """
    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "너는 한국 도서 전문가야. 사용자의 검색 요청을 분석해서 "
                    "알라딘 온라인서점에서 검색할 수 있는 검색어 목록을 만들어.\n\n"
                    "규칙:\n"
                    "1. 실재하는 작가/시인 이름 위주로 추천 (이름은 환각하지 마)\n"
                    "2. 각 검색어를 한 줄에 하나씩, 다른 텍스트 없이\n"
                    "3. '작가이름 장르' 형태로 구성 (예: '박준 시집')\n"
                    "4. 6~8개 검색어\n"
                    "5. 요청의 핵심 장르를 정확히 반영\n\n"
                    "예시:\n"
                    "요청: '요즘 유행하는 mz 시인 시집'\n"
                    "응답:\n"
                    "박준 시집\n"
                    "이별 시집\n"
                    "안현미 시집\n"
                    "김민정 시집\n"
                    "이소호 시집\n"
                    "백은선 시집\n"
                    "한국 현대시 베스트셀러\n"
                    "젊은 시인 시집\n\n"
                    "예시:\n"
                    "요청: '심리 묘사 잘하는 한국 소설'\n"
                    "응답:\n"
                    "한강 소설\n"
                    "김영하 소설\n"
                    "정유정 소설\n"
                    "최은영 소설\n"
                    "김애란 소설\n"
                    "편혜영 소설\n"
                    "한국 심리소설\n"
                    "한국 문학상 수상 소설"
                )},
                {"role": "user", "content": f"{query}"},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        terms = []
        for line in raw.split("\n"):
            line = line.strip().lstrip("0123456789.-) ")
            if not line:
                continue
            terms.append({"search_term": line})

        logger.info(
            "[search-llm] LLM generated %d search terms for query '%s': %s",
            len(terms), query, [t["search_term"] for t in terms],
        )
        return terms[:8]
    except Exception:
        logger.warning("[search-llm] LLM search term generation failed for query '%s'", query)
        return []


async def _seed_from_aladin_for_search(
    db: AsyncSession,
    query: str,
    user_id: UUID | None = None,
) -> int:
    """검색 결과 보완을 위해 알라딘에서 책을 시딩. 새로 시딩된 권수 반환."""
    if user_id:
        from app.services.recommend import _check_seed_limit
        if not _check_seed_limit(user_id):
            logger.info("[search-seed] Daily seed limit reached for user %s", user_id)
            return 0

    # 1) LLM이 검색어 목록 생성 (작가이름 + 장르 조합)
    search_terms = await _suggest_search_terms_via_llm(query)

    # 2) 각 검색어로 알라딘 검색
    aladin_results = []
    seen_isbns_local: set[str] = set()  # 이번 검색 내 중복 방지
    for term_info in search_terms:
        search_term = term_info["search_term"]
        try:
            results = await aladin_search(search_term, max_results=3)
            for r in results:
                if r.isbn and r.isbn in seen_isbns_local:
                    continue
                aladin_results.append(r)
                if r.isbn:
                    seen_isbns_local.add(r.isbn)
            logger.info(
                "[search-seed] Aladin '%s' -> %d results",
                search_term, len(results),
            )
        except Exception:
            logger.warning("[search-seed] Aladin search failed for '%s'", search_term)

    # 3) LLM 검색어 결과 없으면 원본 쿼리로 폴백
    if not aladin_results:
        logger.info("[search-seed] No LLM search results, falling back to query '%s'", query)
        try:
            aladin_results = await aladin_search(query, max_results=MAX_ALADIN_SEED)
        except Exception:
            logger.warning("[search-seed] Fallback Aladin search failed for '%s'", query)
            return 0

    if not aladin_results:
        return 0

    # Collect existing ISBNs and title+author pairs for dedup
    all_books_result = await db.execute(select(Book))
    all_books = all_books_result.scalars().all()
    existing_isbns = {b.isbn for b in all_books if b.isbn}
    existing_title_author = {
        (b.title.strip().lower(), (b.author or "").strip().lower())
        for b in all_books
    }

    seeded = 0
    for item in aladin_results:
        if item.isbn and item.isbn in existing_isbns:
            continue
        title_key = (item.title.strip().lower(), item.author.strip().lower())
        if title_key in existing_title_author:
            continue
        if not item.description:
            continue

        book = Book(
            title=(item.title or "")[:500],
            author=(item.author or "")[:1000],
            isbn=item.isbn,
            description=item.description,
            cover_image_url=(item.cover_image_url or "")[:500],
            genre=(item.genre or "")[:500],
            published_at=item.published_at,
        )
        db.add(book)
        await db.flush()

        try:
            await index_book(book)
            seeded += 1
            if item.isbn:
                existing_isbns.add(item.isbn)
            existing_title_author.add(title_key)
            logger.info("[search-seed] Indexed '%s' by %s", item.title, item.author)
        except Exception:
            logger.warning("[search-seed] Failed to index '%s'", item.title)

    if seeded > 0:
        await db.commit()
        if user_id:
            from app.services.recommend import _increment_seed_count
            _increment_seed_count(user_id)

    logger.info("[search-seed] Seeded %d books from Aladin for query '%s'", seeded, query)
    return seeded


async def search_books_hybrid(
    query: str,
    db: AsyncSession | None = None,
    user_id: UUID | None = None,
    limit: int = 10,
) -> list[dict]:
    """키워드(BM25)와 KNN 벡터 검색을 결합한 하이브리드 검색.

    db가 제공되면, 결과가 부실할 때 알라딘 API로 보완 검색 후 재검색.
    book_id, score, title, author, description을 포함하는 dict 리스트 반환.
    """
    query_embedding, _ = await embed_text(query)

    # 1. 기존 OpenSearch 검색
    results = _do_opensearch_query(query, query_embedding, limit)

    # 2. 결과 부실 판단 + 알라딘 보완 (db가 있을 때만)
    #    - 결과 수 부족 또는 최고 점수가 낮으면 알라딘에서 보완
    #    - 벡터 검색 특성상 관련 없는 결과도 0.5+ 나오므로 임계값을 높게 설정
    logger.debug(
        "[search-debug] db=%s user_id=%s results_count=%d top_score=%.3f",
        db, user_id, len(results), results[0]["score"] if results else 0,
    )
    if db is not None:
        top_score = results[0]["score"] if results else 0.0
        is_insufficient = (
            len(results) < limit or top_score < MIN_SCORE_THRESHOLD
        )
        if is_insufficient:
            logger.info(
                "[search] Insufficient results (count=%d, top_score=%.3f), "
                "supplementing from Aladin for query='%s'",
                len(results), top_score, query,
            )
            seeded = await _seed_from_aladin_for_search(db, query, user_id)
            if seeded > 0:
                results = _do_opensearch_query(query, query_embedding, limit)

    return results


async def knn_search(
    vector: list[float],
    k: int = 10,
    exclude_book_ids: list[str] | None = None,
) -> list[dict]:
    """순수 KNN 검색. 특정 book_id 목록을 제외할 수 있음."""
    _ensure_index_lazy()
    body: dict = {
        "size": k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": vector,
                    "k": k,
                }
            }
        },
    }

    if exclude_book_ids:
        body["query"] = {
            "bool": {
                "must": [body["query"]],
                "must_not": [
                    {"terms": {"book_id": exclude_book_ids}}
                ],
            }
        }

    response = os_client.search(index=INDEX_NAME, body=body)
    hits = response.get("hits", {}).get("hits", [])

    return [
        {
            "book_id": hit["_source"]["book_id"],
            "score": hit["_score"],
            "title": hit["_source"].get("title", ""),
            "author": hit["_source"].get("author", ""),
            "description": hit["_source"].get("description", ""),
            "genre": hit["_source"].get("genre", ""),
        }
        for hit in hits
    ]
