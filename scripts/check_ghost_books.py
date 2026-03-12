"""
OpenSearch에는 존재하지만 PostgreSQL DB에는 없는 '유령 책(Ghost Books)'을 탐지하고 정리하는 스크립트.

사용법:
    # 확인만 하기 (Dry run)
    python scripts/check_ghost_books.py
    docker compose exec -w /project backend python scripts/check_ghost_books.py

    # 확인 후 삭제하기
    python scripts/check_ghost_books.py --delete
    docker compose exec -w /project backend python scripts/check_ghost_books.py --delete
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# backend 패키지 경로 추가
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from opensearchpy import helpers
from sqlalchemy import select

from app.core.database import async_session
from app.models.book import Book
from app.opensearch.client import os_client
from app.opensearch.index import BOOKS_INDEX

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def check_ghosts(delete: bool = False) -> None:
    """유령 책 탐지 및 삭제."""
    logger.info("=== Ghost Book Checker ===")

    # 1. DB에 있는 모든 Book ID 수집
    logger.info("[1/3] DB에서 책 ID 수집 중...")
    async with async_session() as db:
        result = await db.execute(select(Book.id))
        db_ids = {str(bid) for bid in result.scalars().all()}
    logger.info(f"DB 책 수: {len(db_ids)}권")

    # 2. OpenSearch에 있는 모든 Book ID 수집
    logger.info(f"[2/3] OpenSearch '{BOOKS_INDEX}' 인덱스 스캔 중...")
    os_ids = set()
    try:
        if not os_client.indices.exists(index=BOOKS_INDEX):
            logger.error(f"인덱스 '{BOOKS_INDEX}'가 존재하지 않습니다.")
            return

        # helpers.scan은 scroll API를 사용하여 전체 문서를 효율적으로 가져옴
        for doc in helpers.scan(
            os_client,
            query={"query": {"match_all": {}}},
            index=BOOKS_INDEX,
            _source=False,  # ID만 필요하므로 source 제외
        ):
            os_ids.add(doc["_id"])
    except Exception as e:
        logger.error(f"OpenSearch 연결 실패: {e}")
        return
    logger.info(f"OpenSearch 문서 수: {len(os_ids)}개")

    # 3. 비교 (차집합: OpenSearch - DB)
    logger.info("[3/3] 데이터 비교 중...")
    ghost_ids = os_ids - db_ids

    if not ghost_ids:
        logger.info("✅ 데이터 무결성 확인됨: 유령 책이 없습니다.")
        return

    logger.warning(f"⚠️  유령 책 발견: {len(ghost_ids)}개 (OpenSearch에는 있지만 DB에는 없음)")
    
    # 일부 ID 출력
    sample = list(ghost_ids)[:5]
    logger.info(f"예시 IDs: {sample} ...")

    if delete:
        logger.info(f"🗑️  유령 책 {len(ghost_ids)}개 삭제 시작...")
        
        actions = [
            {"_op_type": "delete", "_index": BOOKS_INDEX, "_id": gid}
            for gid in ghost_ids
        ]
        
        success, failed = helpers.bulk(os_client, actions, raise_on_error=False, stats_only=True)
        logger.info(f"삭제 완료: 성공 {success}개, 실패 {failed}개")
        
        # 삭제 후 인덱스 새로고침
        os_client.indices.refresh(index=BOOKS_INDEX)
    else:
        logger.info("💡 삭제하려면 '--delete' 옵션을 사용하세요.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenSearch Ghost Books Cleaner")
    parser.add_argument("--delete", action="store_true", help="탐지된 유령 책을 OpenSearch에서 삭제")
    args = parser.parse_args()

    asyncio.run(check_ghosts(args.delete))
