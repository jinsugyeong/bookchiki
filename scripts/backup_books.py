"""
books OpenSearch 인덱스 전체를 JSON 파일로 백업.

백업 방법: scroll API로 전체 문서 덤프 (임베딩 벡터 포함).
복원 시 OpenAI 재임베딩 없이 그대로 적재 가능.

사용법:
    python scripts/backup_books.py
    python scripts/backup_books.py --output /path/to/backup.json
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = SCRIPT_DIR.parent / "backups"
INDEX_NAME = "books"


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="books OpenSearch 인덱스 백업")
    parser.add_argument(
        "--output",
        default=None,
        help="저장할 JSON 파일 경로 (기본값: backups/books_{timestamp}.json)",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_BACKUP_DIR / f"{INDEX_NAME}_{timestamp}.json"

    from backup_rag_knowledge import backup_index
    count = backup_index(INDEX_NAME, output_path)

    if count == 0:
        logger.error("[backup] 백업 실패")
        sys.exit(1)

    logger.info("[backup] 성공: %d개 문서 백업 완료", count)


if __name__ == "__main__":
    main()
