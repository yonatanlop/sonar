"""Rizoma: fecha de denuncia + historial de eventos de las cuentas de atacantes

- case_records.reported_date: fecha en que se denunció la publicación (para el balance de denuncias).
- case_account_events: historial de cada cuenta (registro, denuncias, eliminaciones, cuenta nueva…).
  Se rellena con lo que ya existe: los eventos con fecha real conservan su fecha; los que hoy no
  tienen fecha quedan con event_date NULL ("sin fecha") para no inventar picos falsos.

Revision ID: 051
Revises: 050
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("case_records", sa.Column("reported_date", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "case_account_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["case_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_case_account_events_account", "case_account_events", ["account_id", "created_at"])
    op.create_index("ix_case_account_events_type_date", "case_account_events", ["event_type", "event_date"])

    # ── Relleno con el estado actual ──────────────────────────────
    # Cuenta registrada / publicación agregada: fecha real = fecha de registro en el sistema.
    op.execute("""
        INSERT INTO case_account_events (account_id, case_id, event_type, event_date, detail, created_by, created_at)
        SELECT id, case_id, 'account_created', created_at, NULL, created_by, created_at FROM case_accounts
    """)
    op.execute("""
        INSERT INTO case_account_events (account_id, case_id, event_type, event_date, detail, created_by, created_at)
        SELECT account_id, case_id, 'post_added', created_at, jsonb_build_object('post_id', post_id), created_by, created_at
        FROM case_records
    """)
    # Estados actuales: la fecha es la registrada (o NULL = sin fecha).
    op.execute("""
        INSERT INTO case_account_events (account_id, case_id, event_type, event_date, detail, created_by, created_at)
        SELECT account_id, case_id, 'report_added', reported_date, jsonb_build_object('post_id', post_id), created_by, created_at
        FROM case_records WHERE reported IS TRUE
    """)
    op.execute("""
        INSERT INTO case_account_events (account_id, case_id, event_type, event_date, detail, created_by, created_at)
        SELECT account_id, case_id, 'post_removed', post_removed_date, jsonb_build_object('post_id', post_id), created_by, created_at
        FROM case_records WHERE post_removed IS TRUE
    """)
    op.execute("""
        INSERT INTO case_account_events (account_id, case_id, event_type, event_date, detail, created_by, created_at)
        SELECT id, case_id, 'account_closed', removed_date, NULL, created_by, created_at
        FROM case_accounts WHERE account_removed IS TRUE
    """)
    op.execute("""
        INSERT INTO case_account_events (account_id, case_id, event_type, event_date, detail, created_by, created_at)
        SELECT id, case_id, 'new_account_created', NULL, jsonb_build_object('info', new_account_info), created_by, created_at
        FROM case_accounts WHERE created_new_account IS TRUE
    """)


def downgrade():
    op.drop_index("ix_case_account_events_type_date", table_name="case_account_events")
    op.drop_index("ix_case_account_events_account", table_name="case_account_events")
    op.drop_table("case_account_events")
    op.drop_column("case_records", "reported_date")
