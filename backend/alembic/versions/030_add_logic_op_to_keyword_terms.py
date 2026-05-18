"""add logic_op and secondary_term to twitter_keyword_terms

Revision ID: 030
Revises: 029
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('twitter_keyword_terms',
        sa.Column('secondary_term', sa.String(200), nullable=True))
    op.add_column('twitter_keyword_terms',
        sa.Column('logic_op', sa.String(3), nullable=False, server_default='AND'))


def downgrade():
    op.drop_column('twitter_keyword_terms', 'logic_op')
    op.drop_column('twitter_keyword_terms', 'secondary_term')
