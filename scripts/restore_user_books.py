"""
user_books OpenSearch 인덱스 복원 (재임베딩 없이).

backup_user_books.py로 생성한 JSON 덤프 파일을 읽어
임베딩 벡터 포함 그대로 OpenSearch에 재적재합니다.

사용법:
    python scripts/restore_user_books.py --input backups/user_books_20250222_120000.json
    python scripts/restore_user_books.py --input backup.json --clear  # 기존 인덱스 초기화 후 복원
"""

import argparse
import logging
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))               # scripts/ (restore_rag_knowledge 임포트용)
sys.path.insert(0, str(SCRIPT_DIR.parent))        # /app (Docker)
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "backend"))  # /repo/backend (host)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

INDEX_NAME = "user_books"


def _ensure_user_books_index(os_client, clear: bool) -> None:
    """user_books 인덱스 준비. clear=True이면 기존 인덱스 삭제 후 재생성."""
    from app.opensearch.index import ensure_user_books_index

    if clear and os_client.indices.exists(index=INDEX_NAME):
        logger.warning("[restore] 기존 인덱스 '%s' 삭제 중 (--clear 옵션)...", INDEX_NAME)
        os_client.indices.delete(index=INDEX_NAME)
        logger.info("[restore] 인덱스 '%s' 삭제 완료", INDEX_NAME)

    ensure_user_books_index()


def restore_user_books(input_path: Path, clear: bool) -> int:
    """백업 파일에서 user_books 인덱스를 복원합니다.

    Args:
        input_path: 백업 JSON 파일 경로
        clear: True이면 기존 인덱스 삭제 후 복원

    Returns:
        복원된 문서 수
    """
    from app.opensearch.client import os_client
    from restore_rag_knowledge import _load_backup, _bulk_restore, BULK_BATCH_SIZE

    meta, documents = _load_backup(input_path)

    if not documents:
        logger.error("[restore] 복원할 문서가 없습니다.")
        return 0

    logger.info("[restore] 복원 대상 인덱스: '%s', 문서 수: %d", INDEX_NAME, len(documents))

    if clear:
        logger.warning(
            "[restore] --clear 옵션: 기존 '%s' 인덱스의 모든 데이터가 삭제됩니다.", INDEX_NAME
        )
        confirm = input("[restore] 계속 하려면 'yes'를 입력하세요: ").strip()
        if confirm.lower() != "yes":
            logger.info("[restore] 취소되었습니다.")
            return 0

    _ensure_user_books_index(os_client, clear)

    logger.info("[restore] 인덱싱 시작 (배치 크기: %d)...", BULK_BATCH_SIZE)
    indexed, errors = _bulk_restore(os_client, INDEX_NAME, documents)

    try:
        actual_count = os_client.count(index=INDEX_NAME)["count"]
    except Exception:
        actual_count = indexed

    logger.info(
        "[restore] 완료: 성공=%d, 실패=%d, 인덱스 총 문서수=%d",
        indexed, errors, actual_count,
    )

    return indexed


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="user_books OpenSearch 인덱스 복원 (재임베딩 없이)")
    parser.add_argument("--input", required=True, help="복원할 JSON 백업 파일 경로")
    parser.add_argument(
        "--clear",
        action="store_true",
        default=False,
        help="기존 인덱스 삭제 후 복원 (주의: 기존 데이터 전체 삭제)",
    )
    args = parser.parse_args()

    count = restore_user_books(Path(args.input), args.clear)

    if count == 0:
        logger.error("[restore] 복원 실패")
        sys.exit(1)

    logger.info("[restore] 성공: %d개 문서 복원 완료", count)


if __name__ == "__main__":
    main()
