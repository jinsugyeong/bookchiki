"""
rag_knowledge OpenSearch 인덱스 복원 (재임베딩 없이).

backup_rag_knowledge.py로 생성한 JSON 덤프 파일을 읽어
임베딩 벡터 포함 그대로 OpenSearch에 재적재합니다.

사용법:
    python scripts/restore_rag_knowledge.py --input backups/rag_knowledge_20250222_120000.json
    python scripts/restore_rag_knowledge.py --input /path/to/backup.json --index rag_knowledge
    python scripts/restore_rag_knowledge.py --input backup.json --clear  # 기존 인덱스 초기화 후 복원
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# backend 패키지 경로 추가
# Docker 내부: /app/scripts → parent = /app (app/ 패키지가 바로 있음)
# 호스트: /repo/scripts → parent.parent/backend = /repo/backend
SCRIPT_DIR = Path(__file__).resolve().parent
_docker_path = SCRIPT_DIR.parent          # /app (Docker)
_host_path = SCRIPT_DIR.parent.parent / "backend"  # /repo/backend (host)
sys.path.insert(0, str(_docker_path))
sys.path.insert(0, str(_host_path))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# 배치당 bulk 인덱싱 문서 수
BULK_BATCH_SIZE = 200


def _load_backup(input_path: Path) -> tuple[dict, list[dict]]:
    """
    백업 JSON 파일을 로드합니다.

    Args:
        input_path: 백업 파일 경로

    Returns:
        (meta, documents) 튜플
    """
    if not input_path.exists():
        raise FileNotFoundError(f"백업 파일을 찾을 수 없습니다: {input_path}")

    file_size_mb = input_path.stat().st_size / (1024 * 1024)
    logger.info("[restore] 백업 파일 로드 중: %s (%.1f MB)", input_path, file_size_mb)

    with open(input_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    meta = backup_data.get("meta", {})
    documents = backup_data.get("documents", [])

    logger.info(
        "[restore] 백업 메타 - 인덱스: %s, 백업일시: %s, 문서수: %d",
        meta.get("index"),
        meta.get("backed_up_at"),
        meta.get("document_count"),
    )

    return meta, documents


def _ensure_target_index(os_client, index_name: str, clear: bool) -> None:
    """
    복원 대상 인덱스를 준비합니다.

    clear=True이면 기존 인덱스를 삭제 후 재생성합니다.
    clear=False이면 존재하지 않을 때만 생성합니다.

    Args:
        os_client: OpenSearch 클라이언트
        index_name: 인덱스명
        clear: True이면 기존 인덱스 삭제 후 재생성
    """
    from app.opensearch.index import ensure_knowledge_index, RAG_KNOWLEDGE_INDEX

    if clear and os_client.indices.exists(index=index_name):
        logger.warning("[restore] 기존 인덱스 '%s' 삭제 중 (--clear 옵션)...", index_name)
        os_client.indices.delete(index=index_name)
        logger.info("[restore] 인덱스 '%s' 삭제 완료", index_name)

    if index_name == RAG_KNOWLEDGE_INDEX:
        ensure_knowledge_index()
    elif not os_client.indices.exists(index=index_name):
        logger.warning(
            "[restore] 인덱스 '%s'가 없습니다. 수동으로 생성이 필요할 수 있습니다.", index_name
        )


def _bulk_restore(os_client, index_name: str, documents: list[dict]) -> tuple[int, int]:
    """
    문서 목록을 배치로 bulk 인덱싱합니다.

    _id를 원본 그대로 사용하여 멱등성을 보장합니다.

    Args:
        os_client: OpenSearch 클라이언트
        index_name: 인덱스명
        documents: [{"_id": ..., "_source": {...}} , ...] 목록

    Returns:
        (indexed_count, error_count) 튜플
    """
    from opensearchpy import helpers as os_helpers

    total_indexed = 0
    total_errors = 0
    total = len(documents)

    for i in range(0, total, BULK_BATCH_SIZE):
        batch = documents[i : i + BULK_BATCH_SIZE]

        actions = [
            {
                "_index": index_name,
                "_id": doc["_id"],
                "_source": doc["_source"],
            }
            for doc in batch
        ]

        try:
            success, failed = os_helpers.bulk(
                os_client,
                actions,
                raise_on_error=False,
                stats_only=True,
            )
            total_indexed += success
            total_errors += failed
        except Exception as e:
            logger.error("[restore] Bulk 인덱싱 실패 (batch %d): %s", i // BULK_BATCH_SIZE, e)
            total_errors += len(batch)

        done = min(i + BULK_BATCH_SIZE, total)
        logger.info(
            "[restore] 진행중: %d / %d (%.1f%%) | 성공: %d, 실패: %d",
            done, total, done / total * 100, total_indexed, total_errors,
        )

    return total_indexed, total_errors


def restore_index(input_path: Path, index_name: str | None, clear: bool) -> int:
    """
    백업 파일에서 OpenSearch 인덱스를 복원합니다.

    Args:
        input_path: 백업 JSON 파일 경로
        index_name: 복원 대상 인덱스명 (None이면 백업 메타의 인덱스명 사용)
        clear: True이면 기존 인덱스 삭제 후 복원

    Returns:
        복원된 문서 수
    """
    from app.opensearch.client import os_client

    # 백업 파일 로드
    meta, documents = _load_backup(input_path)

    if not documents:
        logger.error("[restore] 복원할 문서가 없습니다.")
        return 0

    # 대상 인덱스명 결정
    target_index = index_name or meta.get("index", "rag_knowledge")
    logger.info("[restore] 복원 대상 인덱스: '%s', 문서 수: %d", target_index, len(documents))

    if clear:
        logger.warning(
            "[restore] --clear 옵션: 기존 '%s' 인덱스의 모든 데이터가 삭제됩니다.", target_index
        )
        confirm = input("[restore] 계속 하려면 'yes'를 입력하세요: ").strip()
        if confirm.lower() != "yes":
            logger.info("[restore] 취소되었습니다.")
            return 0

    # 인덱스 준비
    _ensure_target_index(os_client, target_index, clear)

    # Bulk 복원
    logger.info("[restore] 인덱싱 시작 (배치 크기: %d)...", BULK_BATCH_SIZE)
    indexed, errors = _bulk_restore(os_client, target_index, documents)

    # 최종 문서 수 확인
    try:
        actual_count = os_client.count(index=target_index)["count"]
    except Exception:
        actual_count = indexed

    logger.info(
        "[restore] 완료: 성공=%d, 실패=%d, 인덱스 총 문서수=%d",
        indexed, errors, actual_count,
    )

    return indexed


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(
        description="rag_knowledge OpenSearch 인덱스 복원 (재임베딩 없이)"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="복원할 JSON 백업 파일 경로",
    )
    parser.add_argument(
        "--index",
        default=None,
        help="복원 대상 인덱스명 (기본값: 백업 파일 내 index 값)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        default=False,
        help="기존 인덱스 삭제 후 복원 (주의: 기존 데이터 전체 삭제)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    count = restore_index(input_path, args.index, args.clear)

    if count == 0:
        logger.error("[restore] 복원 실패")
        sys.exit(1)

    logger.info("[restore] 성공: %d개 문서 복원 완료", count)


if __name__ == "__main__":
    main()
