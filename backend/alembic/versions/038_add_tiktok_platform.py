"""add tiktok platform

Revision ID: 038
Revises: 037
Create Date: 2026-05-24
"""
from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO social_platforms (name, code, active)
        VALUES ('TikTok', 'tiktok', true)
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM social_platforms WHERE code = 'tiktok'")
