import uuid
from datetime import date, datetime

from sqlalchemy import String, Text, Date, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    isbn: Mapped[str | None] = mapped_column(String(13), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    genre: Mapped[str | None] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_books: Mapped[list["UserBook"]] = relationship(back_populates="book")
    generated_images: Mapped[list["GeneratedImage"]] = relationship(back_populates="book")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="book")
