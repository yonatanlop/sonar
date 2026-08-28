"""Seguimiento a caso: nivel Cuenta/Perfil (Caso → Cuenta → Publicación)

Introduce case_accounts (una cuenta por red social de la persona). Agrupa las
publicaciones ya cargadas en cuentas usando (caso, medio, user_id||author) —
así une variantes del mismo perfil (p.ej. "Cesar Soto"/"César Soto" con igual
user_id) — copia los datos de perfil a la cuenta y elimina esas columnas de
case_records, que ahora cuelga de una cuenta.

Revision ID: 047
Revises: 046
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None

# Clave de agrupación: user_id si existe, si no el author (case-insensitive)
_GROUP_KEY = "lower(coalesce(nullif(trim({t}.user_id), ''), {t}.author, ''))"


def upgrade():
    op.create_table(
        "case_accounts",
        sa.Column("id",      UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("medium",      sa.String(30),   nullable=True),
        sa.Column("author",      sa.String(300),  nullable=True),
        sa.Column("profile_url", sa.String(1000), nullable=True),
        sa.Column("user_id",     sa.String(100),  nullable=True),
        sa.Column("account_age_months", sa.String(300), nullable=True),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("following", sa.Integer(), nullable=True),
        sa.Column("verified",  sa.Boolean(), nullable=True),
        sa.Column("bio",  sa.Text(),      nullable=True),
        sa.Column("city", sa.String(200), nullable=True),
        sa.Column("account_removed",     sa.Boolean(),               nullable=True),
        sa.Column("removed_date",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_new_account", sa.Boolean(),               nullable=True),
        sa.Column("new_account_info",    sa.String(1000),            nullable=True),
        sa.Column("created_by", UUID(as_uuid=True),        nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_case_accounts_case_id", "case_accounts", ["case_id"])

    # Crear una cuenta por grupo (caso, medio, user_id||author)
    op.execute(
        f"""
        INSERT INTO case_accounts (
            id, case_id, medium, author, user_id,
            account_age_months, followers, following, verified, bio, city,
            created_by, created_at
        )
        SELECT
            gen_random_uuid(), case_id, medium,
            max(author), max(nullif(trim(user_id), '')),
            max(account_age_months), max(followers), max(following),
            bool_or(verified), max(bio), max(city),
            min(created_by), min(created_at)
        FROM case_records
        GROUP BY case_id, medium, {_GROUP_KEY.format(t='case_records')}
        """
    )

    # Vincular cada publicación a su cuenta
    op.add_column("case_records", sa.Column("account_id", UUID(as_uuid=True), nullable=True))
    op.execute(
        f"""
        UPDATE case_records r
        SET account_id = a.id
        FROM case_accounts a
        WHERE a.case_id = r.case_id
          AND a.medium IS NOT DISTINCT FROM r.medium
          AND {_GROUP_KEY.format(t='a')} = {_GROUP_KEY.format(t='r')}
        """
    )

    op.alter_column("case_records", "account_id", nullable=False)
    op.create_index("ix_case_records_account_id", "case_records", ["account_id"])
    op.create_foreign_key(
        "fk_case_records_account_id", "case_records", "case_accounts",
        ["account_id"], ["id"], ondelete="CASCADE",
    )

    # Los datos de perfil ahora viven en la cuenta → eliminarlos de la publicación
    with op.batch_alter_table("case_records") as batch:
        for col in (
            "medium", "author", "user_id", "account_age_months",
            "followers", "following", "verified", "bio", "city",
        ):
            batch.drop_column(col)


def downgrade():
    with op.batch_alter_table("case_records") as batch:
        batch.add_column(sa.Column("medium", sa.String(30), nullable=True))
        batch.add_column(sa.Column("author", sa.String(300), nullable=True))
        batch.add_column(sa.Column("user_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("account_age_months", sa.String(300), nullable=True))
        batch.add_column(sa.Column("followers", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("following", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("verified", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("bio", sa.Text(), nullable=True))
        batch.add_column(sa.Column("city", sa.String(200), nullable=True))

    # Restaurar los datos de perfil desde la cuenta
    op.execute(
        """
        UPDATE case_records r
        SET medium = a.medium, author = a.author, user_id = a.user_id,
            account_age_months = a.account_age_months, followers = a.followers,
            following = a.following, verified = a.verified, bio = a.bio, city = a.city
        FROM case_accounts a
        WHERE a.id = r.account_id
        """
    )

    op.drop_constraint("fk_case_records_account_id", "case_records", type_="foreignkey")
    op.drop_index("ix_case_records_account_id", table_name="case_records")
    op.drop_column("case_records", "account_id")

    op.drop_index("ix_case_accounts_case_id", table_name="case_accounts")
    op.drop_table("case_accounts")
