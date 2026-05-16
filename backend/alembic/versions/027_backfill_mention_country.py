"""backfill country_code en menciones desde entidad

Revision ID: 027
Revises: 026
Create Date: 2026-05-16
"""
from alembic import op

revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade():
    # Propaga el country_code de la entidad a todas las menciones que lo tienen NULL.
    # Seguro repetir (IF no tiene efecto si ya está relleno).
    op.execute("""
        UPDATE mentions m
        SET country_code = e.country_code
        FROM entities e
        WHERE m.entity_id = e.id
          AND m.country_code IS NULL
          AND e.country_code IS NOT NULL
    """)


def downgrade():
    pass
