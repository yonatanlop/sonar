"""mention_id in alerts + negative_mention rule type

Revision ID: 020
Revises: 019
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar nuevo valor al enum de PostgreSQL
    op.execute("ALTER TYPE alert_rule_type ADD VALUE IF NOT EXISTS 'negative_mention'")

    # Agregar columna mention_id a la tabla alerts
    op.add_column(
        'alerts',
        sa.Column(
            'mention_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('mentions.id', ondelete='SET NULL'),
            nullable=True,
        )
    )
    op.create_index('ix_alerts_mention_id', 'alerts', ['mention_id'])


def downgrade():
    op.drop_index('ix_alerts_mention_id', table_name='alerts')
    op.drop_column('alerts', 'mention_id')
    # No se puede eliminar un valor de enum en PostgreSQL sin recrear el tipo
