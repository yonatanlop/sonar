"""
Entidades internas de los Explorer.

Cada Explorer (Twitter, Facebook, Instagram, TikTok) y la búsqueda global de Twitter
crean una entidad interna cuyo tipo empieza por "Monitor " (Monitor Twitter, Monitor
Facebook, ...). Son búsquedas ad-hoc, no entidades parametrizadas por el usuario
(Líderes / Instituciones / Keywords), así que NO deben mezclarse con el Dashboard ni
con la sección de Entidades. Este módulo centraliza esa regla.
"""
from sqlalchemy import select

from app.models.entity import Entity, EntityType

EXPLORER_TYPE_LIKE = "Monitor %"


def explorer_type_ids_subq():
    """IDs de los tipos de entidad que pertenecen a un Explorer."""
    return select(EntityType.id).where(EntityType.name.like(EXPLORER_TYPE_LIKE))


def explorer_entity_ids_subq():
    """IDs de las entidades internas de los Explorer."""
    return (
        select(Entity.id)
        .join(EntityType, Entity.entity_type_id == EntityType.id)
        .where(EntityType.name.like(EXPLORER_TYPE_LIKE))
    )
