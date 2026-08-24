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
    Registro dentro de un caso — una publicación denunciada y su trámite.

    Guarda la publicación (fecha, URL, plataforma), la descripción de lo que se
    hizo en la denuncia, el resultado y la fecha de ejecución del resultado.
    """
    __tablename__ = "case_records"

    id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Publicación denunciada
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publication_url:  Mapped[str | None]      = mapped_column(String(1000), nullable=True)
    platform:         Mapped[str | None]      = mapped_column(String(30), nullable=True)  # X, Facebook, YouTube, TikTok, Instagram

    # Trámite de la denuncia
    action_description: Mapped[str | None] = mapped_column(Text, nullable=True)  # qué se realizó en la denuncia
    result:             Mapped[str | None] = mapped_column(Text, nullable=True)  # resultado de la denuncia
    result_date:        Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # fecha de ejecución del resultado

    created_by: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    case:    Mapped["Case"] = relationship("Case", back_populates="records")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
