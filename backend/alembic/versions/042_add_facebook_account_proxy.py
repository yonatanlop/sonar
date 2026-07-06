"""Proxy residencial por cuenta de Facebook: columna proxy_url

Revision ID: 042
Revises: 041
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "facebook_accounts",
        sa.Column("proxy_url", sa.String(500), nullable=True),
    )


def downgrade():
    op.drop_column("facebook_accounts", "proxy_url")
