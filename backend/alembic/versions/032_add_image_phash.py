"""add image_phash to mentions

Revision ID: 032
Revises: 031
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "mentions",
        sa.Column("image_phash", sa.String(64), nullable=True,
                  comment="pHash perceptual de la primera imagen de media_urls (hex)"),
    )
    op.create_index("ix_mentions_image_phash", "mentions", ["image_phash"])


def downgrade():
    op.drop_index("ix_mentions_image_phash", table_name="mentions")
    op.drop_column("mentions", "image_phash")
