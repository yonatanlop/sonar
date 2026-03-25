import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MentionEntity(Base):
    """Entidad nombrada (persona/org/lugar) extraída de una mención por NER."""
    __tablename__ = "mention_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mentions.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(10), nullable=False)   # PER | ORG | LOC
    entity_text: Mapped[str] = mapped_column(String(200), nullable=False)

    mention: Mapped["Mention"] = relationship("Mention")
