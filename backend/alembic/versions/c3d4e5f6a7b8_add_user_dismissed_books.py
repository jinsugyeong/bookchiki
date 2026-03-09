"""add user_dismissed_books table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_dismissed_books",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_dismissed_books_user_id", "user_dismissed_books", ["user_id"])
    op.create_unique_constraint(
        "uq_user_dismissed_books", "user_dismissed_books", ["user_id", "book_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_dismissed_books", "user_dismissed_books", type_="unique")
    op.drop_index("ix_user_dismissed_books_user_id", table_name="user_dismissed_books")
    op.drop_table("user_dismissed_books")
