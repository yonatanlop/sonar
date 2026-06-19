"""Explorers Facebook/Instagram/TikTok: tablas de feeds y tipos de entidad Monitor

Revision ID: 039
Revises: 038
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


_FEEDS = {
    "facebook_feeds":  "Monitor Facebook",
    "instagram_feeds": "Monitor Instagram",
    "tiktok_feeds":    "Monitor TikTok",
}


def _create_feed_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id",           UUID(as_uuid=True),  nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("feed_type",    sa.String(20),        nullable=False),
        sa.Column("term",         sa.String(200),       nullable=False),
        sa.Column("display_name", sa.String(200),       nullable=False),
        sa.Column("entity_id",    UUID(as_uuid=True),   nullable=True),
        sa.Column("active",       sa.Boolean(),         nullable=False, server_default=sa.text("true")),
        sa.Column("is_rizoma",    sa.Boolean(),         nullable=False, server_default=sa.text("false")),
        sa.Column("created_by",   UUID(as_uuid=True),   nullable=False),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["entity_id"],  ["entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],    ondelete="CASCADE"),
    )
    op.create_index(f"ix_{name}_active",    name, ["active"])
    op.create_index(f"ix_{name}_feed_type", name, ["feed_type"])
    op.create_unique_constraint(f"uq_{name}_term_type", name, ["feed_type", "term"])


def upgrade():
    for table, et_name in _FEEDS.items():
        op.execute(f"INSERT INTO entity_types (name) VALUES ('{et_name}') ON CONFLICT DO NOTHING")
        _create_feed_table(table)


def downgrade():
    for table, et_name in _FEEDS.items():
        op.drop_constraint(f"uq_{table}_term_type", table, type_="unique")
        op.drop_index(f"ix_{table}_feed_type", table_name=table)
        op.drop_index(f"ix_{table}_active",    table_name=table)
        op.drop_table(table)
        op.execute(f"DELETE FROM entity_types WHERE name = '{et_name}'")
