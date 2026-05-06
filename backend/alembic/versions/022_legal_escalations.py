"""add legal_escalations table

Revision ID: 022
Revises: 021
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'legal_escalations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('mention_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('mentions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target', sa.String(20), nullable=False),
        sa.Column('snapshot_json', postgresql.JSONB(), nullable=False),
        sa.Column('escalated_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('escalated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('received_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table('legal_escalations')
