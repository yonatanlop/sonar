"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nota: los ENUMs se crean automáticamente por SQLAlchemy
    # al crear cada tabla (create_type=True por defecto).

    # ── Catálogos ─────────────────────────────────────────────────
    op.create_table("countries",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
    )

    op.create_table("entity_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
    )

    op.create_table("social_platforms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), server_default="true"),
    )

    # ── Usuarios ──────────────────────────────────────────────────
    op.create_table("users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(150), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("role", sa.Enum("admin", "analyst", "viewer", name="user_role"), nullable=False, server_default="viewer"),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("telegram_chat_id", sa.String(50)),
        sa.Column("whatsapp_phone", sa.String(20)),
        sa.Column("whatsapp_api_key", sa.String(100)),
        sa.Column("notify_telegram", sa.Boolean(), server_default="true"),
        sa.Column("notify_whatsapp", sa.Boolean(), server_default="false"),
        sa.Column("notify_email", sa.Boolean(), server_default="true"),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
    )

    op.create_table("audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_table", sa.String(50)),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Entidades ─────────────────────────────────────────────────
    op.create_table("entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("entity_type_id", sa.Integer(), sa.ForeignKey("entity_types.id"), nullable=False),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("description", sa.Text()),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table("entity_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table("keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("language", sa.String(2), nullable=False, server_default="es"),
        sa.Column("weight", sa.SmallInteger(), server_default="1"),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Menciones ─────────────────────────────────────────────────
    op.create_table("mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("platform_id", sa.Integer(), sa.ForeignKey("social_platforms.id"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_clean", sa.Text()),
        sa.Column("author_username", sa.String(150)),
        sa.Column("author_ext_id", sa.String(150)),
        sa.Column("url", sa.String(1000)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("language", sa.String(2)),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("sentiment_score", sa.Numeric(4, 3)),
        sa.Column("sentiment_label", sa.Enum("positive", "neutral", "negative", "very_negative", name="sentiment_label")),
        sa.Column("hate_score", sa.Numeric(4, 3)),
        sa.Column("is_hate_speech", sa.Boolean(), server_default="false"),
        sa.Column("is_relevant", sa.Boolean(), server_default="true"),
        sa.Column("reach", sa.Integer(), server_default="0"),
        sa.Column("processed", sa.Boolean(), server_default="false"),
        sa.UniqueConstraint("platform_id", "external_id", name="uq_platform_external_id"),
    )

    op.create_table("mention_keywords",
        sa.Column("mention_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mentions.id"), primary_key=True),
        sa.Column("keyword_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("keywords.id"), primary_key=True),
    )

    # ── Bots ──────────────────────────────────────────────────────
    op.create_table("account_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("platform_id", sa.Integer(), sa.ForeignKey("social_platforms.id"), nullable=False),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("external_user_id", sa.String(150)),
        sa.Column("display_name", sa.String(200)),
        sa.Column("account_created", sa.Date()),
        sa.Column("followers_count", sa.Integer()),
        sa.Column("following_count", sa.Integer()),
        sa.Column("post_count", sa.Integer()),
        sa.Column("has_profile_photo", sa.Boolean()),
        sa.Column("verified", sa.Boolean(), server_default="false"),
        sa.Column("bio", sa.Text()),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("platform_id", "external_user_id", name="uq_platform_user"),
    )

    op.create_table("bot_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("account_profiles.id"), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("bot_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("classification", sa.Enum("real", "anonymous", "bot", "suspicious", name="bot_classification"), nullable=False),
        sa.Column("indicators", postgresql.JSONB()),
        sa.Column("analyzed_by", sa.String(50), server_default="auto"),
    )

    # ── Alertas ───────────────────────────────────────────────────
    op.create_table("alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id")),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("rule_type", sa.Enum("volume_spike", "negative_threshold", "bot_activity", "keyword_critical", "campaign_detected", "hate_speech", name="alert_rule_type"), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("severity", sa.Enum("low", "medium", "high", "critical", name="alert_severity"), nullable=False, server_default="medium"),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table("alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.Enum("low", "medium", "high", "critical", name="alert_severity_val"), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), server_default="false"),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
    )

    # ── Reportes ──────────────────────────────────────────────────
    op.create_table("reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("report_type", sa.Enum("entity", "country", "bots", "alerts", "campaign", name="report_type"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id")),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("file_path", sa.String(500)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Índices ───────────────────────────────────────────────────
    op.create_index("ix_mentions_entity_collected", "mentions", ["entity_id", "collected_at"])
    op.create_index("ix_mentions_processed", "mentions", ["processed"])
    op.create_index("ix_mentions_sentiment", "mentions", ["sentiment_label"])
    op.create_index("ix_alerts_acknowledged", "alerts", ["acknowledged"])
    op.create_index("ix_alerts_entity", "alerts", ["entity_id", "triggered_at"])

    # ── Datos iniciales ───────────────────────────────────────────
    op.execute("""
        INSERT INTO entity_types (name) VALUES
        ('Político'), ('Líder Religioso'), ('Iglesia'),
        ('Partido Político'), ('Tema Específico'), ('Otro')
    """)

    op.execute("""
        INSERT INTO social_platforms (name, code) VALUES
        ('Twitter / X', 'twitter'),
        ('Reddit', 'reddit'),
        ('YouTube', 'youtube'),
        ('Telegram', 'telegram'),
        ('RSS / Noticias', 'rss')
    """)

    op.execute("""
        INSERT INTO countries (code, name) VALUES
        ('CO', 'Colombia'), ('MX', 'México'), ('AR', 'Argentina'),
        ('PE', 'Perú'), ('VE', 'Venezuela'), ('CL', 'Chile'),
        ('EC', 'Ecuador'), ('BO', 'Bolivia'), ('PY', 'Paraguay'),
        ('UY', 'Uruguay'), ('US', 'Estados Unidos'), ('ES', 'España')
    """)


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
    op.drop_table("bot_analysis")
    op.drop_table("account_profiles")
    op.drop_table("mention_keywords")
    op.drop_table("mentions")
    op.drop_table("keywords")
    op.drop_table("entity_aliases")
    op.drop_table("entities")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("social_platforms")
    op.drop_table("entity_types")
    op.drop_table("countries")
    op.execute("DROP TYPE IF EXISTS report_type")
    op.execute("DROP TYPE IF EXISTS alert_severity_val")
    op.execute("DROP TYPE IF EXISTS alert_severity")
    op.execute("DROP TYPE IF EXISTS alert_rule_type")
    op.execute("DROP TYPE IF EXISTS bot_classification")
    op.execute("DROP TYPE IF EXISTS sentiment_label")
    op.execute("DROP TYPE IF EXISTS user_role")
