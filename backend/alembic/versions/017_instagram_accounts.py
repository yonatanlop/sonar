"""instagram_accounts table

Revision ID: 017
Revises: 016
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_accounts",
        sa.Column("id",         sa.Integer(),      primary_key=True, autoincrement=True),
        sa.Column("username",   sa.String(100),    nullable=False),
        sa.Column("password",   sa.String(255),    nullable=False),
        sa.Column("active",     sa.Boolean(),      server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_instagram_accounts_username"),
    )


def downgrade() -> None:
    op.drop_table("instagram_accounts")
