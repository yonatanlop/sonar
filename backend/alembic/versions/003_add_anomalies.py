"""Add anomalies table and extend alert_rule_type enum

Revision ID: 003
Revises: 002
Create Date: 2026-03-25

Cambios:
  1. Extiende el ENUM alert_rule_type con el valor 'anomaly_detected'
  2. Hace nullable alert_rules.created_by (para reglas de sistema automáticas)
  3. Crea la tabla anomalies
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Extender ENUM alert_rule_type ──────────────────────────
    # PostgreSQL no permite ALTER ENUM directamente con op.alter_column,
    # hay que ejecutar ALTER TYPE ... ADD VALUE.
    op.execute("ALTER TYPE alert_rule_type ADD VALUE IF NOT EXISTS 'anomaly_detected'")

    # ── 2. Hacer nullable alert_rules.created_by ──────────────────
    op.alter_column("alert_rules", "created_by", nullable=True)

    # ── 3. Crear tabla anomalies ──────────────────────────────────
    op.create_table(
        "anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("metric",   sa.String(30),  nullable=False),   # "volume" | "negative_pct"
        sa.Column("z_score",  sa.Float(),     nullable=False),
        sa.Column("value",    sa.Float(),     nullable=False),
        sa.Column("baseline", sa.Float(),     nullable=False),
        sa.Column("std_dev",  sa.Float(),     nullable=False),
    )

    op.create_index("ix_anomalies_entity_detected",
                    "anomalies", ["entity_id", "detected_at"])
    op.create_index("ix_anomalies_detected_at",
                    "anomalies", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_anomalies_detected_at",      table_name="anomalies")
    op.drop_index("ix_anomalies_entity_detected",  table_name="anomalies")
    op.drop_table("anomalies")
    op.alter_column("alert_rules", "created_by", nullable=False)
    # Nota: PostgreSQL no permite eliminar valores de un ENUM,
    # se requiere recrear el tipo — omitido en downgrade simple.
