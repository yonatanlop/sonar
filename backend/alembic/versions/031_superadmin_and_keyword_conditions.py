"""superadmin flag + extra_conditions for keyword terms

Revision ID: 031
Revises: 030
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade():
    # Columna is_superadmin en users (default False)
    op.add_column('users',
        sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='false'))

    # Marcar al usuario 'admin' como superadmin automáticamente
    op.execute("UPDATE users SET is_superadmin = true WHERE username = 'admin'")

    # Condiciones adicionales para keywords (array de {term, op})
    # Permite construir queries con 3+ términos y operadores mixtos
    op.add_column('twitter_keyword_terms',
        sa.Column('extra_conditions', JSONB(), nullable=True))


def downgrade():
    op.drop_column('twitter_keyword_terms', 'extra_conditions')
    op.drop_column('users', 'is_superadmin')
