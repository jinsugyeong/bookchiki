"""
PostgreSQL DB 전체를 SQL 덤프 파일로 백업.

pg_dump를 Docker exec로 실행하여 ./backups/ 에 저장합니다.
Docker 없이 psql이 로컬에 설치된 경우에도 직접 실행 가능.

사용법:
    # 호스트에서 실행 (권장 — Docker CLI 필요)
    python scripts/backup_postgres.py
    python scripts/backup_postgres.py --output backups/my_backup.sql

    # pg_dump가 로컬에 설치된 경우 Docker 없이 직접 실행
    python scripts/backup_postgres.py --direct
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# DB 접속 정보. 환경 변수에서 읽어오며, 없으면 개발용 기본값을 사용합니다.
# 운영 환경(EC2)에서는 .env 파일 등을 통해 환경 변수를 설정해야 합니다.
PG_SERVICE = "postgres"     # docker-compose 서비스명
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "bookchiki")
PG_DB = os.getenv("PG_DB", "bookchiki")
PG_PASSWORD = os.getenv("PG_PASSWORD", "bookchiki") # 개발용 기본값. 운영에서는 반드시 환경변수 설정.

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BACKUP_DIR = SCRIPT_DIR.parent / "backups"


def backup_via_docker(output_path: Path) -> bool:
    """docker compose exec 로 pg_dump 실행 후 파일 저장.

    Args:
        output_path: 저장할 .sql 파일 경로

    Returns:
        성공 여부
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "compose", "exec", "-T",
        PG_SERVICE,
        "pg_dump",
        "-U", PG_USER,
        "--no-password",
        PG_DB,
    ]

    logger.info("[backup] pg_dump 실행: %s", " ".join(cmd))
    logger.info("[backup] 저장 경로: %s", output_path)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                # docker compose는 프로젝트 루트에서 실행해야 함
                cwd=str(SCRIPT_DIR.parent),
            )

        if result.returncode != 0:
            logger.error("[backup] pg_dump 실패:\n%s", result.stderr)
            output_path.unlink(missing_ok=True)
            return False

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info("[backup] 완료: %.2f MB → %s", size_mb, output_path)
        return True

    except FileNotFoundError:
        logger.error("[backup] docker 명령어를 찾을 수 없습니다. Docker가 실행 중인지 확인하세요.")
        return False
    except Exception as e:
        logger.error("[backup] 오류: %s", e)
        output_path.unlink(missing_ok=True)
        return False


def backup_via_pg_dump(output_path: Path) -> bool:
    """pg_dump가 로컬에 설치된 경우 직접 실행.

    Args:
        output_path: 저장할 .sql 파일 경로

    Returns:
        성공 여부
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "pg_dump",
        "-h", PG_HOST,
        "-p", PG_PORT,
        "-U", PG_USER,
        "-d", PG_DB,
        "-f", str(output_path),
    ]

    logger.info("[backup] pg_dump 직접 실행: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            # PGPASSWORD 환경 변수를 전달하여 비밀번호 프롬프트 방지
            env=dict(os.environ, PGPASSWORD=PG_PASSWORD),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error("[backup] pg_dump 실패:\n%s", result.stderr)
            return False

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info("[backup] 완료: %.2f MB → %s", size_mb, output_path)
        return True

    except FileNotFoundError:
        logger.error("[backup] pg_dump를 찾을 수 없습니다.")
        return False
    except Exception as e:
        logger.error("[backup] 오류: %s", e)
        return False


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="PostgreSQL DB 백업")
    parser.add_argument(
        "--output",
        default=None,
        help="저장할 .sql 파일 경로 (기본값: backups/bookchiki_{timestamp}.sql)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="docker exec 대신 로컬 pg_dump 직접 실행",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_BACKUP_DIR / f"bookchiki_{timestamp}.sql"

    if args.direct:
        success = backup_via_pg_dump(output_path)
    else:
        success = backup_via_docker(output_path)

    if not success:
        logger.error("[backup] 백업 실패")
        sys.exit(1)

    logger.info("[backup] 성공: %s", output_path)


if __name__ == "__main__":
    main()
