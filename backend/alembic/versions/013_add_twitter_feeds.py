"""Twitter Explorer: tabla twitter_feeds y tipo de entidad Monitor

Revision ID: 013
Revises: 012
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    # Tipo de entidad interno para feeds de Twitter Explorer
    op.execute("INSERT INTO entity_types (name) VALUES ('Monitor Twitter') ON CONFLICT DO NOTHING")

    op.create_table(
        "twitter_feeds",
        sa.Column("id",           UUID(as_uuid=True),  nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("feed_type",    sa.String(20),        nullable=False),   # 'user' | 'hashtag' | 'keyword'
        sa.Column("term",         sa.String(200),       nullable=False),   # username sin @, hashtag sin #, o keyword libre
        sa.Column("display_name", sa.String(200),       nullable=False),   # etiqueta amigable: "@pepito", "#MIRA"
        sa.Column("entity_id",    UUID(as_uuid=True),   nullable=True),    # entity interna auto-creada
        sa.Column("active",       sa.Boolean(),         nullable=False, server_default=sa.text("true")),
        sa.Column("created_by",   UUID(as_uuid=True),   nullable=False),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["entity_id"],  ["entities.id"],  ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],     ondelete="CASCADE"),
    )

    op.create_index("ix_twitter_feeds_active",    "twitter_feeds", ["active"])
    op.create_index("ix_twitter_feeds_feed_type", "twitter_feeds", ["feed_type"])
    op.create_unique_constraint("uq_twitter_feed_term_type", "twitter_feeds", ["feed_type", "term"])


def downgrade():
    op.drop_constraint("uq_twitter_feed_term_type", "twitter_feeds", type_="unique")
    op.drop_index("ix_twitter_feeds_feed_type", table_name="twitter_feeds")
    op.drop_index("ix_twitter_feeds_active",    table_name="twitter_feeds")
    op.drop_table("twitter_feeds")
    op.execute("DELETE FROM entity_types WHERE name = 'Monitor Twitter'")
