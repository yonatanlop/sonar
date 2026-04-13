"""Add Facebook and Instagram to social_platforms

Revision ID: 014
Revises: 013
Create Date: 2026-04-08
"""
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO social_platforms (name, code, active)
        VALUES
            ('Facebook',  'facebook',  true),
            ('Instagram', 'instagram', true)
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM social_platforms WHERE code IN ('facebook', 'instagram')")
