"""Seguimiento a caso: esquema completo del registro (matriz SONAR)

Expande case_records a los ~25 campos que el cliente registra (publicación,
perfil autor, análisis de inautenticidad y estado de la denuncia). Renombra
platform → medium y elimina las columnas de trámite de la versión anterior.

Revision ID: 046
Revises: 045
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("case_records") as batch:
        # Identificación
        batch.add_column(sa.Column("post_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("affects", sa.String(300), nullable=True))
        batch.add_column(sa.Column("sentiment", sa.String(20), nullable=True))
        # Publicación
        batch.add_column(sa.Column("content_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("image_data", sa.Text(), nullable=True))
        batch.add_column(sa.Column("media_type", sa.String(80), nullable=True))
        batch.add_column(sa.Column("likes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("shares", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("comments_count", sa.Integer(), nullable=True))
        # Perfil autor
        batch.add_column(sa.Column("author", sa.String(300), nullable=True))
        batch.add_column(sa.Column("user_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("account_age_months", sa.String(300), nullable=True))
        batch.add_column(sa.Column("followers", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("following", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("verified", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("bio", sa.Text(), nullable=True))
        batch.add_column(sa.Column("city", sa.String(200), nullable=True))
        # Análisis
        batch.add_column(sa.Column("inauthenticity_flag", sa.String(20), nullable=True))
        batch.add_column(sa.Column("organic_criticism", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("opposition_criticism", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("coordinated_attack", sa.Boolean(), nullable=True))
        # Denuncia
        batch.add_column(sa.Column("reporter_name", sa.String(300), nullable=True))
        batch.add_column(sa.Column("reported", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("report_detail", sa.Text(), nullable=True))
        batch.add_column(sa.Column("post_removed", sa.Boolean(), nullable=True))
        # Renombrar plataforma → medio
        batch.alter_column("platform", new_column_name="medium")

    op.create_index("ix_case_records_post_id", "case_records", ["post_id"])

    # Backfill del consecutivo post_id por orden de creación
    op.execute(
        """
        UPDATE case_records cr
        SET post_id = s.seq
        FROM (
            SELECT id, row_number() OVER (ORDER BY created_at, id) AS seq
            FROM case_records
        ) s
        WHERE cr.id = s.id
        """
    )

    # Migrar el antiguo trámite a report_detail antes de eliminar esas columnas
    op.execute(
        """
        UPDATE case_records
        SET report_detail = trim(both E'\n' FROM
            concat_ws(E'\n',
                NULLIF(action_description, ''),
                CASE WHEN result IS NOT NULL AND result <> ''
                     THEN 'Resultado: ' || result END))
        WHERE (action_description IS NOT NULL AND action_description <> '')
           OR (result IS NOT NULL AND result <> '')
        """
    )

    with op.batch_alter_table("case_records") as batch:
        batch.drop_column("action_description")
        batch.drop_column("result")
        batch.drop_column("result_date")


def downgrade():
    with op.batch_alter_table("case_records") as batch:
        batch.add_column(sa.Column("action_description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("result", sa.Text(), nullable=True))
        batch.add_column(sa.Column("result_date", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("medium", new_column_name="platform")

    op.drop_index("ix_case_records_post_id", table_name="case_records")

    with op.batch_alter_table("case_records") as batch:
        for col in (
            "post_removed", "report_detail", "reported", "reporter_name",
            "coordinated_attack", "opposition_criticism", "organic_criticism", "inauthenticity_flag",
            "city", "bio", "verified", "following", "followers", "account_age_months", "user_id", "author",
            "comments_count", "shares", "likes", "media_type", "image_data", "content_text",
            "sentiment", "affects", "post_id",
        ):
            batch.drop_column(col)
