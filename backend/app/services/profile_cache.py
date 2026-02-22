"""
취향 프로필 DB 캐시 관리 서비스.

user_preference_profiles 테이블을 통해 추천 캐시를 관리합니다.
is_dirty=True → 파이프라인 재실행 필요 / is_dirty=False → 캐시 유효.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_preference_profile import UserPreferenceProfile

logger = logging.getLogger(__name__)


async def get_or_create_profile(
    db: AsyncSession,
    user_id: UUID,
) -> UserPreferenceProfile:
    """유저의 취향 프로필을 조회하거나 없으면 새로 생성.

    Args:
        db: 비동기 DB 세션
        user_id: 유저 UUID

    Returns:
        UserPreferenceProfile 인스턴스
    """
    result = await db.execute(
        select(UserPreferenceProfile).where(UserPreferenceProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = UserPreferenceProfile(
            user_id=user_id,
            is_dirty=True,
            version=0,
        )
        db.add(profile)
        await db.flush()
        logger.info("[profile-cache] Created new profile for user %s", user_id)

    return profile


async def mark_profile_dirty(
    db: AsyncSession,
    user_id: UUID,
    reason: str,
) -> None:
    """유저 프로필을 dirty 상태로 마킹 (추천 캐시 무효화).

    Args:
        db: 비동기 DB 세션
        user_id: 유저 UUID
        reason: 무효화 이유 (book_added / book_updated / book_deleted / csv_imported)
    """
    profile = await get_or_create_profile(db, user_id)
    profile.is_dirty = True
    profile.dirty_reason = reason
    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("[profile-cache] Marked dirty for user %s (reason=%s)", user_id, reason)
