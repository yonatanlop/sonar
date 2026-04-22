"""V3 initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = ('v3',)
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(50), nullable=False, unique=True),
        sa.Column('email', sa.String(200), nullable=False, unique=True),
        sa.Column('full_name', sa.String(200), nullable=False),
        sa.Column('hashed_password', sa.String(200), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='viewer'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('telegram_chat_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # ── monitoring ────────────────────────────────────────────────
    op.create_table(
        'countries',
        sa.Column('code', sa.String(2), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
    )
    op.create_table(
        'entity_types',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
    )
    op.create_table(
        'entities',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('entity_type_id', sa.Integer(), sa.ForeignKey('entity_types.id'), nullable=False),
        sa.Column('country_code', sa.String(2), sa.ForeignKey('countries.code'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('monitoring_type', sa.String(20), nullable=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'entity_aliases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('alias', sa.String(200), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'keywords',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('keyword', sa.String(200), nullable=False),
        sa.Column('language', sa.String(2), nullable=False, server_default='es'),
        sa.Column('weight', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'social_platforms',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
    )
    op.create_table(
        'twitter_feeds',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('feed_type', sa.String(20), nullable=False),
        sa.Column('term', sa.String(200), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='SET NULL'), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed social platforms
    op.execute("""
        INSERT INTO social_platforms (name, code, active) VALUES
        ('Twitter / X', 'twitter', true),
        ('YouTube', 'youtube', true),
        ('Reddit', 'reddit', true),
        ('RSS / Noticias', 'rss', true),
        ('Instagram', 'instagram', true),
        ('Facebook', 'facebook', true)
    """)

    # Seed entity types
    op.execute("""
        INSERT INTO entity_types (name) VALUES
        ('Persona'),
        ('Organización'),
        ('Campaña'),
        ('Otro')
    """)


def downgrade() -> None:
    op.drop_table('twitter_feeds')
    op.drop_table('social_platforms')
    op.drop_table('keywords')
    op.drop_table('entity_aliases')
    op.drop_table('entities')
    op.drop_table('entity_types')
    op.drop_table('countries')
    op.drop_table('users')
