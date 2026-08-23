"""Seguimiento a caso: tabla cases

Revision ID: 044
Revises: 043
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cases",
        sa.Column("id",   UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200),     nullable=False),
        sa.Column("image_data",         sa.Text(),                  nullable=True),
        sa.Column("publication_date",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("publication_url",    sa.String(1000),            nullable=True),
        sa.Column("platform",           sa.String(30),              nullable=True),
        sa.Column("action_description", sa.Text(),                  nullable=True),
        sa.Column("result",             sa.Text(),                  nullable=True),
        sa.Column("result_date",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True),        nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_cases_created_at", "cases", ["created_at"])


def downgrade():
    op.drop_index("ix_cases_created_at", table_name="cases")
    op.drop_table("cases")
