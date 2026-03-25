"""Add context_explanation to anomalies and anomaly_id to alerts

Revision ID: 008
Revises: 007
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Explicación de contexto IA en la anomalía
    op.add_column(
        "anomalies",
        sa.Column("context_explanation", sa.Text(), nullable=True),
    )

    # Vínculo directo alerta → anomalía (para mostrar contexto en Alerts.jsx)
    op.add_column(
        "alerts",
        sa.Column(
            "anomaly_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("anomalies.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_alerts_anomaly_id", "alerts", ["anomaly_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_anomaly_id", table_name="alerts")
    op.drop_column("alerts", "anomaly_id")
    op.drop_column("anomalies", "context_explanation")
