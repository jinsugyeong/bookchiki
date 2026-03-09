"""자정 배치 스케줄러.

APScheduler를 사용해 매일 지정 시간에:
1. 모든 유저 추천 재계산 (is_dirty 무관하게 전체 갱신)
2. CF 모델 재학습 (scripts/train_cf.py)
"""

import asyncio
import logging
import subprocess
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.user import User
from app.services.recommend import get_recommendations
from app.services.profile_cache import mark_profile_dirty

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# 배치 실행 시간 (기본 자정 00:00, 환경변수로 오버라이드 가능)
_BATCH_HOUR = int(getattr(settings, "BATCH_HOUR", 0))
_BATCH_MINUTE = int(getattr(settings, "BATCH_MINUTE", 0))


async def _retrain_cf_model() -> None:
    """CF 모델 재학습 (오프라인 스크립트 호출).

    scripts/train_cf.py를 subprocess로 실행.
    """
    script_path = Path("/project/scripts/train_cf.py")
    if not script_path.exists():
        logger.warning("[scheduler] train_cf.py not found, skipping CF retraining")
        return

    logger.info("[scheduler] CF 모델 재학습 시작")
    try:
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            logger.info("[scheduler] CF 모델 재학습 완료")
        else:
            logger.error("[scheduler] CF 재학습 실패: %s", result.stderr[:500])
    except subprocess.TimeoutExpired:
        logger.error("[scheduler] CF 재학습 타임아웃 (10분)")
    except Exception:
        logger.exception("[scheduler] CF 재학습 중 예외 발생")


async def _refresh_all_recommendations() -> None:
    """모든 활성 유저의 추천 재계산.

    1. 전체 유저 is_dirty=true 마킹 (wishlist 변경 반영)
    2. 각 유저 추천 파이프라인 실행
    """
    logger.info("[scheduler] 전체 유저 추천 재계산 시작")

    async with async_session() as db:
        result = await db.execute(select(User.id))
        user_ids = result.scalars().all()

    logger.info("[scheduler] 대상 유저 수: %d명", len(user_ids))

    success = 0
    failed = 0
    for user_id in user_ids:
        try:
            async with async_session() as db:
                # wishlist 포함 전체 서재 변경 반영을 위해 dirty 마킹 후 강제 재계산
                await mark_profile_dirty(db, user_id, reason="batch_refresh")
                await get_recommendations(db, user_id, limit=10, force_refresh=True)
                success += 1
        except Exception:
            logger.exception("[scheduler] 추천 재계산 실패: user=%s", user_id)
            failed += 1

    logger.info(
        "[scheduler] 추천 재계산 완료: 성공=%d 실패=%d", success, failed
    )


async def _run_nightly_batch() -> None:
    """자정 배치 진입점: CF 재학습 → 추천 재계산."""
    logger.info("[scheduler] ===== 자정 배치 시작 =====")
    await _retrain_cf_model()
    await _refresh_all_recommendations()
    logger.info("[scheduler] ===== 자정 배치 완료 =====")


def start_scheduler() -> None:
    """애플리케이션 시작 시 스케줄러 등록."""
    global _scheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_nightly_batch,
        trigger=CronTrigger(hour=_BATCH_HOUR, minute=_BATCH_MINUTE),
        id="nightly_batch",
        name="자정 배치: CF 재학습 + 추천 재계산",
        replace_existing=True,
        misfire_grace_time=3600,  # 1시간 이내 지연 허용
    )
    _scheduler.start()
    logger.info(
        "[scheduler] 스케줄러 시작: 매일 %02d:%02d 배치 실행",
        _BATCH_HOUR,
        _BATCH_MINUTE,
    )


def stop_scheduler() -> None:
    """애플리케이션 종료 시 스케줄러 정지."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] 스케줄러 정지")
