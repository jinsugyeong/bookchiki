import uuid
from datetime import date, datetime

from sqlalchemy import String, SmallInteger, Text, Date, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserBook(Base):
    __tablename__ = "user_books"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="wishlist")  # reading / read / wishlist
    rating: Mapped[int | None] = mapped_column(SmallInteger)  # 1~5
    memo: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[date | None] = mapped_column(Date)  # 읽기 시작한 날짜
    finished_at: Mapped[date | None] = mapped_column(Date)  # 다 읽은 날짜
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual / import
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="user_books")
    book: Mapped["Book"] = relationship(back_populates="user_books")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="user_book", cascade="all, delete-orphan")
