"""alerts action tracking, alert_rules notify_users, entities monitoring_type

Revision ID: 018
Revises: 017
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    # Trazabilidad de alertas
    op.add_column('alerts', sa.Column('action_taken', sa.String(30), nullable=True))
    op.add_column('alerts', sa.Column('action_notes', sa.Text(), nullable=True))

    # Enrutamiento de alertas por usuario
    op.add_column('alert_rules', sa.Column('notify_users', JSONB, nullable=False, server_default='[]'))

    # Categorización de entidades
    op.add_column('entities', sa.Column('monitoring_type', sa.String(20), nullable=True))


def downgrade():
    op.drop_column('alerts', 'action_taken')
    op.drop_column('alerts', 'action_notes')
    op.drop_column('alert_rules', 'notify_users')
    op.drop_column('entities', 'monitoring_type')
