"""
rag_knowledge OpenSearch 인덱스 전체를 JSON 파일로 백업.

백업 방법: scroll API로 전체 문서 덤프 (임베딩 벡터 포함).
복원 시 OpenAI 재임베딩 없이 그대로 적재 가능.

사용법:
    python scripts/backup_rag_knowledge.py
    python scripts/backup_rag_knowledge.py --output /path/to/backup.json
    python scripts/backup_rag_knowledge.py --index books
"""

import argparse
import json
import logging
import sys
from datetime import datetime
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

# 기본 백업 저장 디렉토리
DEFAULT_BACKUP_DIR = SCRIPT_DIR.parent / "backups"

# scroll API 설정
SCROLL_SIZE = 500       # 한 번에 가져오는 문서 수
SCROLL_TIMEOUT = "2m"  # scroll context 유지 시간


def _fetch_all_documents(os_client, index_name: str) -> list[dict]:
    """
    scroll API를 이용해 인덱스 전체 문서를 가져옵니다.

    임베딩 벡터를 포함한 _source 전체를 보존합니다.

    Args:
        os_client: OpenSearch 클라이언트
        index_name: 인덱스명

    Returns:
        문서 딕셔너리 목록 (_id, _source 포함)
    """
    documents = []

    # 첫 번째 scroll 요청
    response = os_client.search(
        index=index_name,
        scroll=SCROLL_TIMEOUT,
        body={"size": SCROLL_SIZE, "query": {"match_all": {}}},
    )

    scroll_id = response["_scroll_id"]
    hits = response["hits"]["hits"]
    total = response["hits"]["total"]["value"]

    logger.info("[backup] 전체 문서 수: %d", total)

    batch_num = 0
    while hits:
        for hit in hits:
            documents.append({"_id": hit["_id"], "_source": hit["_source"]})

        batch_num += 1
        fetched = len(documents)
        logger.info("[backup] 수집 중: %d / %d (%.1f%%)", fetched, total, fetched / total * 100)

        # 다음 배치 요청
        response = os_client.scroll(scroll_id=scroll_id, scroll=SCROLL_TIMEOUT)
        scroll_id = response["_scroll_id"]
        hits = response["hits"]["hits"]

    # scroll context 정리
    try:
        os_client.clear_scroll(scroll_id=scroll_id)
    except Exception:
        pass  # 정리 실패는 치명적이지 않음

    return documents


def _get_index_mapping(os_client, index_name: str) -> dict:
    """
    인덱스 매핑을 가져옵니다 (복원 시 인덱스 재생성에 사용).

    Args:
        os_client: OpenSearch 클라이언트
        index_name: 인덱스명

    Returns:
        인덱스 매핑 딕셔너리
    """
    try:
        mapping = os_client.indices.get_mapping(index=index_name)
        settings = os_client.indices.get_settings(index=index_name)
        return {
            "mappings": mapping.get(index_name, {}).get("mappings", {}),
            "settings": settings.get(index_name, {}).get("settings", {}),
        }
    except Exception as e:
        logger.warning("[backup] 매핑 조회 실패: %s", e)
        return {}


def backup_index(index_name: str, output_path: Path) -> int:
    """
    지정 OpenSearch 인덱스를 JSON 파일로 백업합니다.

    백업 파일 형식:
    {
        "meta": {
            "index": "rag_knowledge",
            "backed_up_at": "2025-02-22T12:00:00",
            "document_count": 3500,
            "opensearch_mapping": {...}
        },
        "documents": [
            {"_id": "abc123", "_source": {"text": ..., "embedding": [...], ...}},
            ...
        ]
    }

    Args:
        index_name: 백업할 인덱스명
        output_path: 저장할 JSON 파일 경로

    Returns:
        백업된 문서 수
    """
    from app.opensearch.client import os_client

    # 인덱스 존재 여부 확인
    if not os_client.indices.exists(index=index_name):
        logger.error("[backup] 인덱스 '%s'가 존재하지 않습니다.", index_name)
        return 0

    logger.info("[backup] 인덱스 '%s' 백업 시작 → %s", index_name, output_path)

    # 매핑 조회
    index_meta = _get_index_mapping(os_client, index_name)

    # 전체 문서 수집
    documents = _fetch_all_documents(os_client, index_name)

    if not documents:
        logger.warning("[backup] 백업할 문서가 없습니다.")
        return 0

    # 백업 파일 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)

    backup_data = {
        "meta": {
            "index": index_name,
            "backed_up_at": datetime.utcnow().isoformat(),
            "document_count": len(documents),
            "opensearch_mapping": index_meta,
        },
        "documents": documents,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=None)  # indent=None으로 파일 크기 절약

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(
        "[backup] 완료: %d개 문서 → %s (%.1f MB)",
        len(documents),
        output_path,
        file_size_mb,
    )

    return len(documents)


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="rag_knowledge OpenSearch 인덱스 백업")
    parser.add_argument(
        "--index",
        default="rag_knowledge",
        help="백업할 인덱스명 (기본값: rag_knowledge)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="저장할 JSON 파일 경로 (기본값: backups/{index}_{timestamp}.json)",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_BACKUP_DIR / f"{args.index}_{timestamp}.json"

    count = backup_index(args.index, output_path)

    if count == 0:
        logger.error("[backup] 백업 실패")
        sys.exit(1)

    logger.info("[backup] 성공: %d개 문서 백업 완료", count)


if __name__ == "__main__":
    main()
