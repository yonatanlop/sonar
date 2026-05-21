"""add mention_replies table

Revision ID: 035
Revises: 034
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mention_replies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("reply_account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("mention_id", UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_reply_url", sa.String(1000), nullable=True),
        sa.Column("logged_by", UUID(as_uuid=True), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reply_account_id"], ["reply_accounts.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mention_id"], ["mentions.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["logged_by"], ["users.id"]),
    )
    op.create_index("ix_mention_replies_account",
                    "mention_replies", ["reply_account_id"])
    op.create_index("ix_mention_replies_mention",
                    "mention_replies", ["mention_id"])
    op.create_index("ix_mention_replies_replied_at",
                    "mention_replies", ["replied_at"])


def downgrade():
    op.drop_index("ix_mention_replies_replied_at",
                  table_name="mention_replies")
    op.drop_index("ix_mention_replies_mention", table_name="mention_replies")
    op.drop_index("ix_mention_replies_account", table_name="mention_replies")
    op.drop_table("mention_replies")
