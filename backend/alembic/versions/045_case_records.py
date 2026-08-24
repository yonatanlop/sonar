"""Seguimiento a caso: casos con múltiples registros (padre → hijos)

Crea la tabla case_records (un registro = una publicación denunciada) y adelgaza
cases a nombre + imagen. Migra cualquier dato de publicación ya cargado en cases
a un registro hijo antes de eliminar esas columnas.

Revision ID: 045
Revises: 044
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "case_records",
        sa.Column("id",      UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("publication_date",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("publication_url",    sa.String(1000),            nullable=True),
        sa.Column("platform",           sa.String(30),              nullable=True),
        sa.Column("action_description", sa.Text(),                  nullable=True),
        sa.Column("result",             sa.Text(),                  nullable=True),
        sa.Column("result_date",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True),        nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_case_records_case_id", "case_records", ["case_id"])

    # Migrar datos existentes: cada caso con alguna columna de publicación cargada
    # se convierte en un registro hijo, para no perder los datos ya ingresados.
    op.execute(
        """
        INSERT INTO case_records (
            id, case_id, publication_date, publication_url, platform,
            action_description, result, result_date, created_by, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), id, publication_date, publication_url, platform,
            action_description, result, result_date, created_by, created_at, updated_at
        FROM cases
        WHERE publication_date   IS NOT NULL
           OR publication_url    IS NOT NULL
           OR platform           IS NOT NULL
           OR action_description IS NOT NULL
           OR result             IS NOT NULL
           OR result_date        IS NOT NULL
        """
    )

    with op.batch_alter_table("cases") as batch:
        batch.drop_column("publication_date")
        batch.drop_column("publication_url")
        batch.drop_column("platform")
        batch.drop_column("action_description")
        batch.drop_column("result")
        batch.drop_column("result_date")


def downgrade():
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("publication_date",   sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("publication_url",    sa.String(1000),            nullable=True))
        batch.add_column(sa.Column("platform",           sa.String(30),              nullable=True))
        batch.add_column(sa.Column("action_description", sa.Text(),                  nullable=True))
        batch.add_column(sa.Column("result",             sa.Text(),                  nullable=True))
        batch.add_column(sa.Column("result_date",        sa.DateTime(timezone=True), nullable=True))

    op.drop_index("ix_case_records_case_id", table_name="case_records")
    op.drop_table("case_records")
