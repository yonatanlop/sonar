import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Case(Base):
    """
    Seguimiento a caso — agrupa múltiples publicaciones denunciadas bajo un
    mismo nombre (ej. "Caso Payita").

    El caso guarda solo el nombre y una imagen opcional (data-URI base64 en
    `image_data`). Cada publicación denunciada es un `CaseRecord` hijo, de modo
    que un caso puede tener N registros de distintas redes sociales.
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
    records: Mapped[list["CaseRecord"]] = relationship(
        "CaseRecord",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseRecord.created_at",
    )


class CaseRecord(Base):
    """
    Registro dentro de un caso — una publicación monitoreada y su denuncia.

    El esquema replica la matriz de seguimiento del cliente (Excel SONAR): datos
    de la publicación, del perfil autor, indicadores de análisis y el estado de
    la denuncia. Todos los campos son opcionales salvo el vínculo al caso.
    """
    __tablename__ = "case_records"

    id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
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
    medium:           Mapped[str | None]      = mapped_column(String(30), nullable=True)    # Facebook, Instagram, TikTok, YouTube, X, Sitio Web, Threads
    media_type:       Mapped[str | None]      = mapped_column(String(80), nullable=True)    # Video / Publicación / Columna / Otro
    likes:            Mapped[int | None]      = mapped_column(nullable=True)                 # nº de me gusta
    shares:           Mapped[int | None]      = mapped_column(nullable=True)                 # compartidos / retweets
    comments_count:   Mapped[int | None]      = mapped_column(nullable=True)                 # nº de comentarios

    # Perfil autor
    author:             Mapped[str | None] = mapped_column(String(300), nullable=True)  # quién hace la publicación
    user_id:            Mapped[str | None] = mapped_column(String(100), nullable=True)  # user id
    account_age_months: Mapped[str | None] = mapped_column(String(300), nullable=True)  # antigüedad de la cuenta (meses) — texto libre
    followers:          Mapped[int | None] = mapped_column(nullable=True)               # nº de seguidores
    following:          Mapped[int | None] = mapped_column(nullable=True)               # nº de seguidos
    verified:           Mapped[bool | None] = mapped_column(nullable=True)              # ¿cuenta verificada?
    bio:                Mapped[str | None] = mapped_column(Text, nullable=True)         # biografía/descripción del perfil
    city:               Mapped[str | None] = mapped_column(String(200), nullable=True)  # ciudad de origen

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

    case:    Mapped["Case"] = relationship("Case", back_populates="records")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
