"""add reply_accounts table

Revision ID: 034
Revises: 033
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reply_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["social_platforms.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_reply_accounts_platform", "reply_accounts", ["platform_id"])
    op.create_index("ix_reply_accounts_active", "reply_accounts", ["active"])


def downgrade():
    op.drop_index("ix_reply_accounts_active", table_name="reply_accounts")
    op.drop_index("ix_reply_accounts_platform", table_name="reply_accounts")
    op.drop_table("reply_accounts")
