"""Pool de cuentas Facebook: tabla facebook_accounts

Revision ID: 041
Revises: 040
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "facebook_accounts",
        sa.Column("id",           sa.Integer(),  nullable=False, autoincrement=True),
        sa.Column("label",        sa.String(150), nullable=False),
        sa.Column("cookies_json", sa.Text(),      nullable=False),
        sa.Column("active",       sa.Boolean(),   nullable=False, server_default=sa.text("true")),
        sa.Column("last_used",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facebook_accounts_active", "facebook_accounts", ["active"])


def downgrade():
    op.drop_index("ix_facebook_accounts_active", table_name="facebook_accounts")
    op.drop_table("facebook_accounts")
