import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserDismissedBook(Base):
    """사용자가 '다른 책' 버튼으로 영구 비추천한 책 목록.

    사용자가 직접 서재에 추가하면 해당 레코드 자동 삭제.
    """

    __tablename__ = "user_dismissed_books"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_user_dismissed_books"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="dismissed_books")
    book: Mapped["Book"] = relationship()
