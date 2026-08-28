import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Case(Base):
    """
    Seguimiento a caso — la persona/sujeto monitoreado (ej. "Caso Payita").

    Jerarquía de 3 niveles: Caso → Cuenta (perfil por red social) → Publicación.
    El caso guarda solo el nombre y una imagen opcional; los datos del perfil
    viven en `CaseAccount` (una por red social) y las publicaciones en
    `CaseRecord` (colgando de cada cuenta).
    """
    __tablename__ = "cases"

    id:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]       = mapped_column(String(200), nullable=False)

    # Imagen opcional del caso (data-URI base64: "data:image/png;base64,...")
    image_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    accounts: Mapped[list["CaseAccount"]] = relationship(
        "CaseAccount",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseAccount.created_at",
    )


class CaseAccount(Base):
    """
    Cuenta / perfil de una persona en una red social (ej. Payita en TikTok).

    Agrupa las publicaciones (`CaseRecord`) de esa cuenta, de modo que los datos
    del perfil se cargan una sola vez por red. Incluye el estado de la cuenta:
    si fue eliminada y si la persona creó una cuenta nueva para seguir atacando.
    """
    __tablename__ = "case_accounts"

    id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Identidad de la cuenta
    medium:      Mapped[str | None] = mapped_column(String(30), nullable=True)    # red social: Facebook, Instagram, TikTok, YouTube, X, Threads, Sitio Web
    author:      Mapped[str | None] = mapped_column(String(300), nullable=True)   # nombre / quién publica
    profile_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # URL del perfil
    user_id:     Mapped[str | None] = mapped_column(String(100), nullable=True)   # user id

    # Datos del perfil
    account_age_months: Mapped[str | None]  = mapped_column(String(300), nullable=True)  # antigüedad (meses) — texto libre
    followers:          Mapped[int | None]  = mapped_column(nullable=True)               # nº de seguidores
    following:          Mapped[int | None]  = mapped_column(nullable=True)               # nº de seguidos
    verified:           Mapped[bool | None] = mapped_column(nullable=True)               # ¿cuenta verificada?
    bio:                Mapped[str | None]  = mapped_column(Text, nullable=True)         # biografía/descripción
    city:               Mapped[str | None]  = mapped_column(String(200), nullable=True)  # ciudad de origen

    # Estado de la cuenta
    account_removed:     Mapped[bool | None]     = mapped_column(nullable=True)                # ¿la cuenta fue eliminada?
    removed_date:        Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # fecha de eliminación
    created_new_account: Mapped[bool | None]     = mapped_column(nullable=True)                # ¿creó cuenta nueva?
    new_account_info:    Mapped[str | None]      = mapped_column(String(1000), nullable=True)  # nombre/URL de la cuenta nueva

    created_by: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    case:    Mapped["Case"] = relationship("Case", back_populates="accounts")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    records: Mapped[list["CaseRecord"]] = relationship(
        "CaseRecord",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="CaseRecord.created_at",
    )


class CaseRecord(Base):
    """
    Publicación monitoreada dentro de una cuenta.

    Guarda solo lo específico de la publicación (contenido, métricas, análisis de
    inautenticidad y denuncia). Los datos del perfil autor y la red social viven
    en la `CaseAccount` a la que pertenece.
    """
    __tablename__ = "case_records"

    id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Identificación
    post_id: Mapped[int | None] = mapped_column(nullable=True, index=True)  # consecutivo global (0001, 0002…)
    affects: Mapped[str | None] = mapped_column(String(300), nullable=True)  # a quién afecta este contenido
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Positivo / Negativo / Neutral

    # Publicación
    publication_url:  Mapped[str | None]      = mapped_column(String(1000), nullable=True)  # link de la publicación/comentario
    content_text:     Mapped[str | None]      = mapped_column(Text, nullable=True)          # texto del contenido
    image_data:       Mapped[str | None]      = mapped_column(Text, nullable=True)          # captura de imagen (data-URI base64)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # fecha y hora
    media_type:       Mapped[str | None]      = mapped_column(String(80), nullable=True)    # Video / Publicación / Columna / Otro
    likes:            Mapped[int | None]      = mapped_column(nullable=True)                 # nº de me gusta
    shares:           Mapped[int | None]      = mapped_column(nullable=True)                 # compartidos / retweets
    comments_count:   Mapped[int | None]      = mapped_column(nullable=True)                 # nº de comentarios

    # Análisis
    inauthenticity_flag:  Mapped[str | None]  = mapped_column(String(20), nullable=True)  # semáforo: Rojo / Amarillo / Verde
    organic_criticism:    Mapped[bool | None] = mapped_column(nullable=True)  # ¿crítica orgánica de ciudadanos reales?
    opposition_criticism: Mapped[bool | None] = mapped_column(nullable=True)  # ¿crítica impulsada por opositores?
    coordinated_attack:   Mapped[bool | None] = mapped_column(nullable=True)  # ¿ataque coordinado (CIB)?

    # Denuncia
    reporter_name: Mapped[str | None]  = mapped_column(String(300), nullable=True)  # nombre de quien reporta
    reported:      Mapped[bool | None] = mapped_column(nullable=True)               # ¿se denunció?
    report_detail: Mapped[str | None]  = mapped_column(Text, nullable=True)         # detalle de la denuncia
    post_removed:  Mapped[bool | None] = mapped_column(nullable=True)               # ¿la publicación fue eliminada?

    created_by: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    account: Mapped["CaseAccount"] = relationship("CaseAccount", back_populates="records")
    creator: Mapped["User"]        = relationship("User", foreign_keys=[created_by])  # noqa: F821
