"""add unique constraint to account_profiles(platform_id, username)

Revision ID: 036
Revises: 035
Create Date: 2026-05-22
"""
from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade():
    # Eliminar duplicados antes de crear el constraint
    op.execute("""
        DELETE FROM account_profiles a
        USING account_profiles b
        WHERE a.id > b.id
          AND a.platform_id = b.platform_id
          AND a.username = b.username
    """)
    op.create_unique_constraint(
        "uq_account_profiles_platform_username",
        "account_profiles",
        ["platform_id", "username"],
    )


def downgrade():
    op.drop_constraint(
        "uq_account_profiles_platform_username",
        "account_profiles",
        type_="unique",
    )
