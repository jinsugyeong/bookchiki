"""
SQL 덤프 파일에서 PostgreSQL DB 복원.

백업 파일(backup_postgres.py로 생성)을 읽어 DB에 복원합니다.

사용법:
    # 호스트에서 실행 (권장 — Docker CLI 필요)
    python scripts/restore_postgres.py backups/bookchiki_20260223_120000.sql

    # psql이 로컬에 설치된 경우 Docker 없이 직접 실행
    python scripts/restore_postgres.py backups/bookchiki_20260223_120000.sql --direct
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# DB 접속 정보. 환경 변수에서 읽어오며, 없으면 개발용 기본값을 사용합니다.
# 운영 환경(EC2)에서는 .env 파일 등을 통해 환경 변수를 설정해야 합니다.
PG_SERVICE = "postgres"
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "bookchiki")
PG_DB = os.getenv("PG_DB", "bookchiki")
PG_PASSWORD = os.getenv("PG_PASSWORD", "bookchiki") # 개발용 기본값. 운영에서는 반드시 환경변수 설정.

SCRIPT_DIR = Path(__file__).resolve().parent


def restore_via_docker(backup_path: Path) -> bool:
    """docker compose exec 로 psql 실행하여 복원.

    Args:
        backup_path: 복원할 .sql 파일 경로 (호스트 경로)

    Returns:
        성공 여부
    """
    if not backup_path.exists():
        logger.error("[restore] 파일이 존재하지 않습니다: %s", backup_path)
        return False

    cmd = [
        "docker", "compose", "exec", "-T",
        PG_SERVICE,
        "psql",
        "-U", PG_USER,
        "-d", PG_DB,
    ]

    logger.info("[restore] psql 실행: %s", " ".join(cmd))
    logger.info("[restore] 복원 파일: %s", backup_path)

    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True,
                cwd=str(SCRIPT_DIR.parent),
            )

        if result.returncode != 0:
            logger.error("[restore] psql 실패:\n%s", result.stderr)
            return False

        if result.stderr:
            # psql은 정상 실행 중에도 NOTICE 등을 stderr로 출력하는 경우 있음
            logger.debug("[restore] psql stderr:\n%s", result.stderr)

        logger.info("[restore] 완료")
        return True

    except FileNotFoundError:
        logger.error("[restore] docker 명령어를 찾을 수 없습니다.")
        return False
    except Exception as e:
        logger.error("[restore] 오류: %s", e)
        return False


def restore_via_psql(backup_path: Path) -> bool:
    """psql이 로컬에 설치된 경우 직접 실행.

    Args:
        backup_path: 복원할 .sql 파일 경로

    Returns:
        성공 여부
    """
    if not backup_path.exists():
        logger.error("[restore] 파일이 존재하지 않습니다: %s", backup_path)
        return False

    cmd = [
        "psql",
        "-h", PG_HOST,
        "-p", PG_PORT,
        "-U", PG_USER,
        "-d", PG_DB,
        "-f", str(backup_path),
    ]

    logger.info("[restore] psql 직접 실행: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            # PGPASSWORD 환경 변수를 전달하여 비밀번호 프롬프트 방지
            env=dict(os.environ, PGPASSWORD=PG_PASSWORD),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error("[restore] psql 실패:\n%s", result.stderr)
            return False

        logger.info("[restore] 완료")
        return True

    except FileNotFoundError:
        logger.error("[restore] psql을 찾을 수 없습니다.")
        return False
    except Exception as e:
        logger.error("[restore] 오류: %s", e)
        return False


def list_backups() -> None:
    """backups/ 디렉토리의 PostgreSQL 백업 목록 출력."""
    backup_dir = SCRIPT_DIR.parent / "backups"
    sql_files = sorted(backup_dir.glob("bookchiki_*.sql"), reverse=True)

    if not sql_files:
        logger.info("[restore] 백업 파일이 없습니다: %s", backup_dir)
        return

    logger.info("[restore] 사용 가능한 백업 파일 (%d개):", len(sql_files))
    for f in sql_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        logger.info("  %.2f MB  %s", size_mb, f.name)


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="PostgreSQL DB 복원")
    parser.add_argument(
        "backup_file",
        nargs="?",
        default=None,
        help="복원할 .sql 파일 경로 (생략 시 백업 목록 출력)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="docker exec 대신 로컬 psql 직접 실행",
    )
    args = parser.parse_args()

    if args.backup_file is None:
        list_backups()
        return

    backup_path = Path(args.backup_file)

    # 상대 경로면 프로젝트 루트 기준으로 해석
    if not backup_path.is_absolute():
        backup_path = SCRIPT_DIR.parent / backup_path

    logger.info("[restore] ⚠️  현재 DB의 기존 데이터 위에 복원합니다.")
    logger.info("[restore] 파일: %s", backup_path)

    confirm = input("계속하시겠습니까? (y/N): ").strip().lower()
    if confirm != "y":
        logger.info("[restore] 취소됨")
        sys.exit(0)

    if args.direct:
        success = restore_via_psql(backup_path)
    else:
        success = restore_via_docker(backup_path)

    if not success:
        logger.error("[restore] 복원 실패")
        sys.exit(1)

    logger.info("[restore] 성공")


if __name__ == "__main__":
    main()
