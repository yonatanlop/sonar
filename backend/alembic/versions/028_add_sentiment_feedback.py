"""add sentiment_feedback table

Revision ID: 028
Revises: 027
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sentiment_feedback',
        sa.Column('id',              sa.Integer(),             nullable=False, autoincrement=True),
        sa.Column('mention_id',      UUID(as_uuid=True),       nullable=False),
        sa.Column('original_label',  sa.String(20),            nullable=False),
        sa.Column('corrected_label', sa.String(20),            nullable=False),
        sa.Column('analyst_id',      UUID(as_uuid=True),       nullable=False),
        sa.Column('notes',           sa.Text(),                nullable=True),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['mention_id'], ['mentions.id'],  ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analyst_id'], ['users.id'],     ondelete='CASCADE'),
    )
    op.create_index('ix_sentiment_feedback_mention', 'sentiment_feedback', ['mention_id'])
    op.create_index('ix_sentiment_feedback_analyst', 'sentiment_feedback', ['analyst_id'])


def downgrade():
    op.drop_index('ix_sentiment_feedback_analyst', table_name='sentiment_feedback')
    op.drop_index('ix_sentiment_feedback_mention',  table_name='sentiment_feedback')
    op.drop_table('sentiment_feedback')
