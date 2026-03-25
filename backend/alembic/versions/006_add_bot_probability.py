"""Add bot_probability to account_profiles

Revision ID: 006
Revises: 005
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_profiles",
        sa.Column("bot_probability", sa.Float(), nullable=True),
    )
    op.create_index("ix_account_profiles_bot_prob", "account_profiles", ["bot_probability"])


def downgrade() -> None:
    op.drop_index("ix_account_profiles_bot_prob", table_name="account_profiles")
    op.drop_column("account_profiles", "bot_probability")
