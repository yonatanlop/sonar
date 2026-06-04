"""
Búsqueda Twitter por keyword/hashtag.
Activa a las 8 PM COT y busca continuamente hasta que el admin la detenga.
Descarta tweets publicados antes de 2026-05-18 20:00 COT (UTC-5).
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Corte: no guardar tweets anteriores a las 8 PM COT del 18 may 2026
CUTOFF_DT        = datetime(2026, 5, 18, 20, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
MAX_PER_TERM     = 50   # tweets por término por ejecución
DELAY_BETWEEN    = 5    # segundos entre términos
SINCE_DATE       = "2026-05-18"  # filtro Twitter-side (reduce tráfico)

def _build_query(term) -> str:
    """
    Construye la query de Twitter a partir de un TwitterKeywordTerm.

    Agrupa los términos en "corridas de OR" entre paréntesis para preservar la
    intención lógica y mantener la búsqueda anclada al sujeto. Los términos
    conectados por OR forman un grupo (a OR b); los grupos se combinan con AND
    (espacio); los términos NOT se excluyen aparte (-"x").

    Ejemplos:
      Tigre OR Abelardo AND política AND campaña
        → ("Tigre" OR "Abelardo") "política" "campaña"
      Abelardo AND política OR gobierno
        → "Abelardo" ("política" OR "gobierno")
      Abelardo AND falso NOT rumor
        → "Abelardo" "falso" -"rumor"

    El primer grupo SIEMPRE contiene el término principal y es requerido (ancla),
    por lo que ningún OR puede "escaparse" y traer ruido no relacionado.
    """
    if term.term_type == "hashtag":
        tag = term.term.strip().lstrip("#")
        return f"#{tag} since:{SINCE_DATE} -is:retweet lang:es"

    base_filters = f"since:{SINCE_DATE} -is:retweet (lang:es OR lang:en)"

    # Secuencia completa: principal (sin op) + condiciones (cada op conecta con el término previo)
    seq = [{"term": term.term.strip(), "op": None}]
    if term.extra_conditions:
        seq += [
            {"term": (c.get("term") or "").strip(), "op": (c.get("op") or "AND").upper()}
            for c in term.extra_conditions
            if (c.get("term") or "").strip()
        ]
    elif term.secondary_term and term.secondary_term.strip():
        seq.append({"term": term.secondary_term.strip(), "op": (term.logic_op or "AND").upper()})

    # Exclusiones (NOT) se sacan aparte; el resto forma la secuencia positiva
    exclusions = [it["term"] for it in seq if it["op"] == "NOT"]
    positive = [it for it in seq if it["op"] != "NOT"]

    if not positive:
        # Caso extremo: solo el principal
        positive = [seq[0]]

    # Agrupar en corridas de OR: un nuevo grupo empieza en cada AND (o al inicio)
    groups = [[positive[0]["term"]]]
    for it in positive[1:]:
        if it["op"] == "OR":
            groups[-1].append(it["term"])
        else:  # AND
            groups.append([it["term"]])

    parts = []
    for g in groups:
        if len(g) == 1:
            parts.append(f'"{g[0]}"')
        else:
            parts.append("(" + " OR ".join(f'"{t}"' for t in g) + ")")

    parts += [f'-"{t}"' for t in exclusions]

    return f'{" ".join(parts)} {base_filters}'


def _get_or_create_system_entity(db: Session):
    """Devuelve la entidad sistema 'Búsqueda Twitter Global', creándola si no existe."""
    from app.models.entity import Entity, EntityType
    from app.models.user import User

    entity = db.query(Entity).filter(Entity.name == "Búsqueda Twitter Global").first()
    if entity:
        return entity

    # Obtener o crear tipo de entidad
    et = db.query(EntityType).filter(EntityType.name == "Monitor Twitter").first()
    if not et:
        et = EntityType(name="Monitor Twitter")
        db.add(et)
        db.flush()

    # Primer usuario admin como propietario técnico
    admin = db.query(User).filter(User.role == "admin").first()
    if not admin:
        admin = db.query(User).first()
    if not admin:
        raise RuntimeError("[TwitterKeyword] Sin usuarios en la base de datos — no se puede crear entidad sistema")

    entity = Entity(
        name="Búsqueda Twitter Global",
        entity_type_id=et.id,
        country_code="CO",
        active=True,
        created_by=admin.id,
    )
    db.add(entity)
    db.flush()
    logger.info("[TwitterKeyword] Entidad sistema 'Búsqueda Twitter Global' creada (id=%s)", entity.id)
    return entity


async def search_keywords(db: Session) -> dict:
    """
    Ejecuta una ronda de búsqueda para todos los términos activos.
    Retorna dict con estadísticas.  No-op si is_active=False.
    """
    from app.models.twitter_keyword import TwitterKeywordConfig, TwitterKeywordTerm
    from app.models.mention import SocialPlatform
    from app.workers.scrapers.twitter import TwitterScraper, _scrape_feed_query

    config = db.query(TwitterKeywordConfig).first()
    if not config or not config.is_active:
        logger.debug("[TwitterKeyword] Búsqueda inactiva — saltando")
        return {"skipped": True, "reason": "inactive"}

    terms = (
        db.query(TwitterKeywordTerm)
        .filter(TwitterKeywordTerm.is_active == True)
        .all()
    )
    if not terms:
        logger.debug("[TwitterKeyword] Sin términos activos — saltando")
        return {"skipped": True, "reason": "no_terms"}

    platform = db.query(SocialPlatform).filter(SocialPlatform.code == "twitter").first()
    if not platform:
        logger.warning("[TwitterKeyword] Plataforma 'twitter' no encontrada")
        return {"skipped": True, "reason": "no_platform"}

    entity = _get_or_create_system_entity(db)

    # Construir API twscrape (reutiliza el mismo pool de cuentas que TwitterScraper)
    scraper_inst = TwitterScraper.__new__(TwitterScraper)
    scraper_inst.db = db
    tw_api = scraper_inst._build_api()

    # Verificar cuentas disponibles
    all_accounts = await tw_api.pool.get_all()
    active_accounts = [a for a in all_accounts if getattr(a, "active", True)]
    if not active_accounts:
        logger.warning("[TwitterKeyword] Sin cuentas activas — saltando")
        return {"skipped": True, "reason": "no_accounts"}

    total_saved = 0

    for t in terms:
        query = _build_query(t)
        if not query:
            continue

        try:
            saved = await asyncio.wait_for(
                _scrape_keywords_query(
                    tw_api, query, platform.id, entity.id, db,
                    country_code="CO",
                ),
                timeout=15,
            )
            total_saved += saved
            logger.info("[TwitterKeyword] '%s' → %d nuevos tweets", t.term, saved)
        except asyncio.TimeoutError:
            logger.warning("[TwitterKeyword] Timeout en término '%s'", t.term)
        except Exception as exc:
            logger.warning("[TwitterKeyword] Error en término '%s': %s", t.term, exc)

        await asyncio.sleep(DELAY_BETWEEN)

    # Actualizar timestamp de última ejecución
    config.last_run_at = datetime.now(timezone.utc)
    db.add(config)

    return {"terms": len(terms), "saved": total_saved}


async def _scrape_keywords_query(api, query: str, platform_id: int, entity_id, db,
                                  country_code: str | None = None) -> int:
    """Wraps _scrape_feed_query añadiendo el filtro de fecha de corte."""
    import json as _json
    from app.workers.scrapers.base import save_mention, upsert_account_profile

    saved = 0
    try:
        async for tweet in api.search(query, limit=MAX_PER_TERM):
            try:
                # Filtro de fecha de corte
                pub_at = tweet.date
                if pub_at:
                    if not pub_at.tzinfo:
                        pub_at = pub_at.replace(tzinfo=timezone.utc)
                    if pub_at < CUTOFF_DT:
                        continue

                user = tweet.user
                if user:
                    upsert_account_profile(
                        db=db,
                        platform_id=platform_id,
                        username=user.username,
                        external_user_id=str(user.id),
                        display_name=getattr(user, "displayname", None),
                        followers_count=getattr(user, "followersCount", None),
                        following_count=getattr(user, "friendsCount", None),
                        post_count=getattr(user, "statusesCount", None),
                        has_profile_photo=bool(getattr(user, "profileImageUrl", None)),
                        verified=(
                            bool(getattr(user, "verified", False))
                            or bool(getattr(user, "blue", False))
                        ),
                        account_created=(
                            user.created.date() if getattr(user, "created", None) else None
                        ),
                        bio=getattr(user, "rawDescription", None),
                        location_text=(getattr(user, "location", None) or "")[:200] or None,
                    )

                content  = getattr(tweet, "rawContent", None) or tweet.content
                url      = getattr(tweet, "url", f"https://x.com/i/web/status/{tweet.id}")
                reach    = (
                    (getattr(tweet, "likeCount",    0) or 0)
                    + (getattr(tweet, "retweetCount", 0) or 0)
                    + (getattr(tweet, "replyCount",   0) or 0)
                    + (getattr(tweet, "quoteCount",   0) or 0)
                )

                media_urls = None
                try:
                    media = getattr(tweet, "media", None) or []
                    imgs  = [
                        m.url for m in media
                        if hasattr(m, "url") and m.url
                        and any(m.url.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp"))
                    ]
                    if not imgs:
                        imgs = [m.previewUrl for m in media if hasattr(m, "previewUrl") and m.previewUrl]
                    if imgs:
                        media_urls = _json.dumps(imgs[:4])
                except Exception:
                    pass

                mention = save_mention(
                    db=db,
                    platform_id=platform_id,
                    entity_id=entity_id,
                    external_id=str(tweet.id),
                    content=content,
                    author_username=user.username if user else None,
                    author_ext_id=str(user.id) if user else None,
                    url=url,
                    published_at=pub_at,
                    language=getattr(tweet, "lang", None),
                    country_code=country_code,
                    reach=reach,
                    media_urls=media_urls,
                    conversation_id=str(getattr(tweet, "conversationId", None) or "") or None,
                )
                if mention:
                    saved += 1

            except Exception as exc:
                logger.warning("[TwitterKeyword] Error procesando tweet %s: %s",
                               getattr(tweet, "id", "?"), exc)
                continue
    except Exception as exc:
        raise exc

    return saved
