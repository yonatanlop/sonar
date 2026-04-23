from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user, require_analyst
from app.modules.monitoring.application.schemas import (
    EntityCreate, EntityPatch, EntityOut, AliasCreate, AliasOut,
    KeywordCreate, KeywordOut, EntityTypeOut,
)
from app.modules.monitoring.application.monitoring_service import EntityService
from app.modules.monitoring.infrastructure.entity_repository import (
    SqlEntityRepository, SqlEntityAliasRepository, SqlKeywordRepository
)
from app.modules.monitoring.infrastructure.orm import EntityTypeORM

router = APIRouter(prefix="/entities", tags=["Entidades"])


def _svc(db: Session = Depends(get_db)) -> EntityService:
    return EntityService(
        SqlEntityRepository(db),
        SqlEntityAliasRepository(db),
        SqlKeywordRepository(db),
    )


@router.get("/types", response_model=list[EntityTypeOut])
def list_entity_types(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [EntityTypeOut(id=r.id, name=r.name)
            for r in db.query(EntityTypeORM).order_by(EntityTypeORM.name).all()]


@router.get("", response_model=list[EntityOut])
def list_entities(
    active_only: bool = Query(True),
    svc: EntityService = Depends(_svc),
    _=Depends(get_current_user),
):
    entities = svc.list(active_only=active_only)
    return [_to_out(e) for e in entities]


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(entity_id: UUID, svc: EntityService = Depends(_svc), _=Depends(get_current_user)):
    return _to_out(svc.get(entity_id))


@router.post("", response_model=EntityOut, status_code=201)
def create_entity(
    data: EntityCreate,
    svc: EntityService = Depends(_svc),
    current_user=Depends(require_analyst),
):
    return _to_out(svc.create(data, created_by=current_user.id))


@router.patch("/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: UUID,
    data: EntityPatch,
    svc: EntityService = Depends(_svc),
    _=Depends(require_analyst),
):
    return _to_out(svc.update(entity_id, data))


@router.delete("/{entity_id}", status_code=204)
def delete_entity(entity_id: UUID, svc: EntityService = Depends(_svc), _=Depends(require_analyst)):
    svc.delete(entity_id)


# ── Aliases ──────────────────────────────────────────────────
@router.post("/{entity_id}/aliases", response_model=AliasOut, status_code=201)
def add_alias(
    entity_id: UUID,
    data: AliasCreate,
    svc: EntityService = Depends(_svc),
    current_user=Depends(require_analyst),
):
    a = svc.add_alias(entity_id, data, created_by=current_user.id)
    return AliasOut(id=a.id, alias=a.alias)


@router.delete("/{entity_id}/aliases/{alias_id}", status_code=204)
def delete_alias(
    entity_id: UUID,
    alias_id: UUID,
    svc: EntityService = Depends(_svc),
    _=Depends(require_analyst),
):
    svc.delete_alias(alias_id)


# ── Keywords ──────────────────────────────────────────────────
@router.post("/{entity_id}/keywords", response_model=KeywordOut, status_code=201)
def add_keyword(
    entity_id: UUID,
    data: KeywordCreate,
    svc: EntityService = Depends(_svc),
    current_user=Depends(require_analyst),
):
    k = svc.add_keyword(entity_id, data, created_by=current_user.id)
    return KeywordOut(id=k.id, keyword=k.keyword, language=k.language,
                      weight=k.weight, active=k.active)


@router.delete("/{entity_id}/keywords/{keyword_id}", status_code=204)
def delete_keyword(
    entity_id: UUID,
    keyword_id: UUID,
    svc: EntityService = Depends(_svc),
    _=Depends(require_analyst),
):
    svc.delete_keyword(keyword_id)


# ── Helper ────────────────────────────────────────────────────
def _to_out(e) -> EntityOut:
    return EntityOut(
        id=e.id,
        name=e.name,
        entity_type_id=e.entity_type_id,
        country_code=e.country_code,
        description=e.description,
        photo_url=e.photo_url,
        active=e.active,
        monitoring_type=e.monitoring_type,
        created_at=e.created_at,
        aliases=[AliasOut(id=a.id, alias=a.alias) for a in e.aliases],
        keywords=[KeywordOut(id=k.id, keyword=k.keyword, language=k.language,
                             weight=k.weight, active=k.active) for k in e.keywords],
    )
