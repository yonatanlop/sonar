"""Sección Grupos: tabla facebook_groups (gestión de cierre de grupos)

Revision ID: 040
Revises: 039
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "facebook_groups",
        sa.Column("id",         UUID(as_uuid=True),  nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_url",  sa.String(500),       nullable=False),
        sa.Column("reason",     sa.Text(),            nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True),   nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_facebook_groups_created_at", "facebook_groups", ["created_at"])


def downgrade():
    op.drop_index("ix_facebook_groups_created_at", table_name="facebook_groups")
    op.drop_table("facebook_groups")
