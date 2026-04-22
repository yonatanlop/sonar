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

    # ── collection ────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'instagram_accounts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('password', sa.String(255), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'mentions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('platform_id', sa.Integer(), sa.ForeignKey('social_platforms.id'), nullable=False),
        sa.Column('external_id', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_clean', sa.Text(), nullable=True),
        sa.Column('author_username', sa.String(150), nullable=True),
        sa.Column('author_ext_id', sa.String(150), nullable=True),
        sa.Column('url', sa.String(1000), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('language', sa.String(2), nullable=True),
        sa.Column('country_code', sa.String(2), sa.ForeignKey('countries.code'), nullable=True),
        sa.Column('sentiment_score', sa.Numeric(4, 3), nullable=True),
        sa.Column('sentiment_label', sa.Enum('positive', 'neutral', 'negative', 'very_negative',
                                              name='sentiment_label'), nullable=True),
        sa.Column('hate_score', sa.Numeric(4, 3), nullable=True),
        sa.Column('is_hate_speech', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_relevant', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('reach', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('urgency_score', sa.Numeric(5, 1), nullable=False, server_default='0'),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('topic_label', sa.String(120), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('conversation_id', sa.String(50), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('media_urls', sa.Text(), nullable=True),
        sa.Column('visual_match', sa.Boolean(), nullable=True),
        sa.Column('visual_match_names', sa.Text(), nullable=True),
        sa.Column('embedding', sa.Text(), nullable=True),  # pgvector vector(384)
        sa.UniqueConstraint('platform_id', 'external_id', name='uq_platform_external_id'),
    )
    op.create_table(
        'mention_keywords',
        sa.Column('mention_id', sa.String(36), sa.ForeignKey('mentions.id'), primary_key=True),
        sa.Column('keyword_id', sa.String(36), sa.ForeignKey('keywords.id'), primary_key=True),
    )
    op.create_table(
        'account_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('platform_id', sa.Integer(), sa.ForeignKey('social_platforms.id'), nullable=False),
        sa.Column('username', sa.String(150), nullable=False),
        sa.Column('external_user_id', sa.String(150), nullable=True),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('account_created', sa.Date(), nullable=True),
        sa.Column('followers_count', sa.Integer(), nullable=True),
        sa.Column('following_count', sa.Integer(), nullable=True),
        sa.Column('post_count', sa.Integer(), nullable=True),
        sa.Column('has_profile_photo', sa.Boolean(), nullable=True),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('location_text', sa.String(200), nullable=True),
        sa.Column('last_analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bot_probability', sa.Numeric(5, 4), nullable=True),
        sa.UniqueConstraint('platform_id', 'external_user_id', name='uq_platform_user'),
    )
    op.create_table(
        'bot_analysis',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_profile_id', sa.String(36), sa.ForeignKey('account_profiles.id'), nullable=False),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('bot_score', sa.Numeric(4, 3), nullable=False),
        sa.Column('classification', sa.Enum('real', 'anonymous', 'bot', 'suspicious',
                                             name='bot_classification'), nullable=False),
        sa.Column('indicators', sa.JSON(), nullable=True),
        sa.Column('analyzed_by', sa.String(50), nullable=False, server_default='auto'),
    )
    # Replace embedding column with proper pgvector type after creation
    op.execute("ALTER TABLE mentions DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE mentions ADD COLUMN embedding vector(384)")

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
    op.drop_table('bot_analysis')
    op.drop_table('account_profiles')
    op.drop_table('mention_keywords')
    op.drop_table('mentions')
    op.drop_table('instagram_accounts')
    op.drop_table('twitter_feeds')
    op.drop_table('social_platforms')
    op.drop_table('keywords')
    op.drop_table('entity_aliases')
    op.drop_table('entities')
    op.drop_table('entity_types')
    op.drop_table('countries')
    op.drop_table('users')
    op.execute("DROP TYPE IF EXISTS sentiment_label")
    op.execute("DROP TYPE IF EXISTS bot_classification")
