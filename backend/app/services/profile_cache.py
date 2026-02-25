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


async def update_profile(
    db: AsyncSession,
    user_id: UUID,
    profile_data: dict,
    preference_vector: list[float] | None,
) -> None:
    """프로필 데이터 및 취향 벡터 갱신 후 is_dirty=False로 전환.

    Args:
        db: 비동기 DB 세션
        user_id: 유저 UUID
        profile_data: 취향 프로필 JSONB (preferred_genres, preference_summary 등)
        preference_vector: 1536차원 취향 벡터 (None이면 cold start)
    """
    now = datetime.now(timezone.utc)
    profile = await get_or_create_profile(db, user_id)

    profile.profile_data = profile_data
    profile.preference_vector = preference_vector
    profile.is_dirty = False
    profile.dirty_reason = None
    profile.version = profile.version + 1
    profile.profile_computed_at = now
    if preference_vector is not None:
        profile.vector_computed_at = now
    profile.updated_at = now

    await db.flush()
    logger.info(
        "[profile-cache] Updated profile for user %s (version=%d, has_vector=%s)",
        user_id,
        profile.version,
        preference_vector is not None,
    )


async def is_recommendation_fresh(
    db: AsyncSession,
    user_id: UUID,
) -> bool:
    """캐시가 신선한지 (is_dirty=False) 확인.

    Returns:
        True이면 캐시 유효 (recommendations 테이블 직접 조회 가능)
    """
    profile = await get_or_create_profile(db, user_id)
    fresh = not profile.is_dirty
    logger.info(
        "[profile-cache] Freshness check for user %s: fresh=%s (dirty_reason=%s)",
        user_id,
        fresh,
        profile.dirty_reason,
    )
    return fresh


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
