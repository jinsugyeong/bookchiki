import uuid
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ImageVersion(Base):
    __tablename__ = "image_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generated_image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_images.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    text_elements: Mapped[dict | None] = mapped_column(JSONB)  # font, color, position, text content
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    generated_image: Mapped["GeneratedImage"] = relationship(back_populates="versions")
