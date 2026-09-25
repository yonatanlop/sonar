"""Actividad coordinada: grupos detectados y sus publicaciones

Tablas para la detección de actividad coordinada (etapa 2 de bots): coordination_clusters (grupos
candidatos con estado de revisión) y coordination_members (publicaciones de cada grupo).

Revision ID: 050
Revises: 049
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "coordination_clusters",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entity_name", sa.String(200), nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accounts_count", sa.Integer(), nullable=False),
        sa.Column("mentions_count", sa.Integer(), nullable=False),
        sa.Column("span_hours", sa.Float(), nullable=True),
        sa.Column("median_followers", sa.Integer(), nullable=True),
        sa.Column("low_follower_share", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sentiment_mix", JSONB(), nullable=True),
        sa.Column("sample_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="nuevo"),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
    )
    op.create_index("ix_coordination_clusters_score", "coordination_clusters", ["score"])
    op.create_index("ix_coordination_clusters_status", "coordination_clusters", ["status"])

    op.create_table(
        "coordination_members",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cluster_id", UUID(as_uuid=True), nullable=False),
        sa.Column("mention_id", UUID(as_uuid=True), nullable=False),
        sa.Column("account_profile_id", UUID(as_uuid=True), nullable=True),
        sa.Column("author_username", sa.String(150), nullable=True),
        sa.Column("author_ext_id", sa.String(150), nullable=True),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("account_created", sa.Date(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cluster_id"], ["coordination_clusters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mention_id"], ["mentions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_profile_id"], ["account_profiles.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_coordination_members_cluster_id", "coordination_members", ["cluster_id"])
    op.create_index("ix_coordination_members_mention_id", "coordination_members", ["mention_id"])
    op.create_index("ix_coordination_members_account_profile_id", "coordination_members", ["account_profile_id"])
    op.create_index("ix_coordination_members_author_ext_id", "coordination_members", ["author_ext_id"])


def downgrade():
    op.drop_table("coordination_members")
    op.drop_table("coordination_clusters")
