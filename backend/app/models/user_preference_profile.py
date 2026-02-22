import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserPreferenceProfile(Base):
    """사용자 취향 프로필 및 추천 캐시 테이블.

    is_dirty=True이면 캐시가 무효화된 상태 → 파이프라인 재실행 필요.
    is_dirty=False이면 캐시 유효 → recommendations 테이블 직접 조회.
    """

    __tablename__ = "user_preference_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # 취향 프로필 데이터 (LLM이 생성)
    # 구조: { preferred_genres, disliked_genres, preference_summary, top_rated_books, reading_count, memo_analyzed_at }
    profile_data: Mapped[dict | None] = mapped_column(JSONB)

    # 취향 벡터 (OpenAI embed, 1536차원, JSONB 직렬화)
    preference_vector: Mapped[list | None] = mapped_column(JSONB)

    # 캐시 무효화 신호
    is_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dirty_reason: Mapped[str | None] = mapped_column(String(100))  # book_added / book_updated / book_deleted / csv_imported

    # 낙관적 동시성 제어
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 마지막 계산 시각
    profile_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vector_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="preference_profile")
