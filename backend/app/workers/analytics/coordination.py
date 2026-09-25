"""
Detección de actividad coordinada (CIB) — etapa 2 de la detección de bots.

Los metadatos de una cuenta (bio, antigüedad, ratio) detectan poco. Lo que revela una campaña
coordinada es el COMPORTAMIENTO ENTRE CUENTAS: el mismo texto (o casi) publicado por cuentas distintas
en una ventana corta. Es lo que los analistas del cliente describen a mano en el Drive
("varias personas coordinadamente", "mismos correos enviados desde diferentes cuentas").

Enfoque (sin modelo entrenado; no hay referencia etiquetada suficiente en X):
  1. Se toman las menciones de entidades monitoreadas de Twitter/YouTube (RSS se excluye: los medios
     se copian titulares de forma normal) en los últimos N días.
  2. Se normalizan los textos (sin URLs, @menciones, tildes ni puntuación) y se agrupan los
     casi-duplicados con MinHash + LSH (Jaccard >= 0.6 sobre trigramas de palabras, <= 72 h,
     cuentas distintas).
  3. Cada grupo con >= 3 cuentas distintas se puntúa (0-1) combinando: nº de cuentas, compresión
     temporal, cuentas con pocos seguidores, cuentas jóvenes y cuentas que se repiten en varios
     grupos ("núcleo de la red"). Si la mediana de seguidores es alta (medios, cuentas reales) el
     puntaje se atenúa.
  4. También se detecta la REPETICIÓN: una sola cuenta publicando el mismo texto >= 5 veces.
El resultado son CANDIDATOS: el equipo los confirma o descarta en la pantalla "Actividad coordinada",
y esas decisiones son la referencia real para calibrar el detector.
"""
import logging
import random
import unicodedata
import zlib
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Optional

logger = logging.getLogger(__name__)

JACCARD_MIN = 0.6
WINDOW_HOURS = 72
MIN_TOKENS = 8
MIN_ACCOUNTS_NETWORK = 3
MIN_REPEATS = 5
MAX_BUCKET = 60

_N_PERM = 32
_MASK = (1 << 61) - 1
_BANDS, _ROWS = 8, 4
_rng = random.Random(7)
_PERMS = [(_rng.randrange(1, _MASK), _rng.randrange(0, _MASK)) for _ in range(_N_PERM)]


# ── Normalización y agrupamiento (funciones puras, probadas con datos reales) ──────────

def normalize_tokens(text: str) -> list:
    """Minúsculas, sin tildes, sin URLs ni @menciones ni puntuación."""
    t = unicodedata.normalize("NFD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    out = []
    for tok in t.split():
        if tok.startswith("http") or tok.startswith("@"):
            continue
        tok = "".join(c for c in tok if c.isalnum())
        if tok:
            out.append(tok)
    return out


def _shingles(toks: list, k: int = 3) -> set:
    return {zlib.crc32(" ".join(toks[i:i + k]).encode()) for i in range(len(toks) - k + 1)}


def cluster_documents(docs: list) -> list:
    """
    docs: [{"toks": [...], "ts": datetime, "author": str}, ...]
    Devuelve una lista de clusters (listas de índices de docs) con >= 2 cuentas distintas.
    """
    # Solo se guardan las firmas MinHash (32 enteros por documento). Los trigramas se recalculan bajo
    # demanda al verificar pares candidatos: conservarlos todos costaba ~270 MB con 19.500 documentos
    # y rozaba el límite de 288 MB del contenedor.
    sigs = []
    for d in docs:
        s = _shingles(d["toks"])
        sigs.append([min((a * x + b) & _MASK for x in s) for a, b in _PERMS] if s else None)

    buckets = defaultdict(list)
    for i, sg in enumerate(sigs):
        if sg is None:
            continue
        for bnd in range(_BANDS):
            buckets[(bnd, tuple(sg[bnd * _ROWS:(bnd + 1) * _ROWS]))].append(i)

    parent = list(range(len(docs)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen_pairs = set()
    for members in buckets.values():
        if not (1 < len(members) <= MAX_BUCKET):
            continue
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                pair = (members[a], members[b])
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                i, j = pair
                if docs[i]["author"] == docs[j]["author"]:
                    continue
                if abs((docs[i]["ts"] - docs[j]["ts"]).total_seconds()) > WINDOW_HOURS * 3600:
                    continue
                si, sj = _shingles(docs[i]["toks"]), _shingles(docs[j]["toks"])
                union = len(si | sj)
                if union and len(si & sj) / union >= JACCARD_MIN:
                    parent[find(i)] = find(j)

    groups = defaultdict(list)
    for i in range(len(docs)):
        groups[find(i)].append(i)
    return [g for g in groups.values() if len({docs[i]["author"] for i in g}) >= 2]


def score_network(n_accounts: int, span_hours: float, low_follower_share: float,
                  young_share: float, repeat_share: float, median_followers: Optional[int]) -> float:
    """Puntaje 0-1 de un grupo de cuentas con texto casi idéntico (ver docstring del módulo)."""
    s_n = min((n_accounts - 1) / 6.0, 1.0)                 # 3 cuentas → .33 ; 7+ → 1
    s_t = 1.0 if span_hours <= 6 else 0.7 if span_hours <= 24 else 0.4
    score = 0.30 * s_n + 0.20 * s_t + 0.20 * low_follower_share + 0.10 * young_share + 0.20 * repeat_share
    if median_followers is not None and median_followers >= 5000:
        score *= 0.3                                        # medios / cuentas reales: sindicación normal
    return round(max(0.0, min(score, 1.0)), 3)


# ── Detección sobre la base de datos ───────────────────────────────────────────────────

def _load_documents(db, days: int, max_rows: int) -> list:
    from app.core.explorer import explorer_entity_ids_subq
    from app.models.bot import AccountProfile
    from app.models.entity import Entity
    from app.models.mention import Mention, SocialPlatform
    from sqlalchemy import and_, func

    since = datetime.now(timezone.utc) - timedelta(days=days)
    ts_col = func.coalesce(Mention.published_at, Mention.collected_at)
    rows = (
        db.query(
            Mention.id, Mention.content, Mention.author_username, Mention.author_ext_id, ts_col.label("ts"),
            Mention.sentiment_label, Mention.url, Mention.entity_id, Entity.name.label("entity_name"),
            SocialPlatform.name.label("platform"), AccountProfile.id.label("profile_id"),
            AccountProfile.followers_count, AccountProfile.account_created,
        )
        .join(Entity, Entity.id == Mention.entity_id)
        .join(SocialPlatform, SocialPlatform.id == Mention.platform_id)
        .outerjoin(AccountProfile, and_(AccountProfile.platform_id == Mention.platform_id,
                                        AccountProfile.external_user_id == Mention.author_ext_id))
        .filter(
            Mention.is_relevant == True,  # noqa: E712
            Mention.collected_at >= since,
            Mention.author_ext_id.isnot(None),
            SocialPlatform.code.in_(["twitter", "youtube"]),
            ~Mention.entity_id.in_(explorer_entity_ids_subq()),
        )
        .order_by(ts_col.desc())
        .limit(max_rows)
        .all()
    )
    docs = []
    for r in rows:
        toks = normalize_tokens(r.content)
        if len(toks) < MIN_TOKENS:
            continue
        ts = r.ts if r.ts.tzinfo else r.ts.replace(tzinfo=timezone.utc)
        docs.append({
            "toks": toks, "ts": ts, "author": r.author_ext_id, "mention_id": r.id, "content": r.content or "",
            "username": r.author_username, "sentiment": r.sentiment_label, "url": r.url,
            "entity_id": r.entity_id, "entity_name": (r.entity_name or "").strip(), "platform": r.platform,
            "profile_id": r.profile_id, "followers": r.followers_count, "created": r.account_created,
        })
    return docs


def _cluster_metrics(docs: list, idxs: list, kind: str, repeat_counts: dict) -> dict:
    members = [docs[i] for i in idxs]
    ts = sorted(m["ts"] for m in members)
    accounts = {}
    for m in members:
        accounts.setdefault(m["author"], m)
    fol = [a["followers"] for a in accounts.values() if a["followers"] is not None]
    med_fol = int(median(fol)) if fol else None
    n_acc = len(accounts)
    span = (ts[-1] - ts[0]).total_seconds() / 3600.0
    low = sum(1 for a in accounts.values() if a["followers"] is not None and a["followers"] < 300)
    low_share = low / max(len(fol), 1) if fol else 0.0
    first_day = ts[0].date()
    young = sum(1 for a in accounts.values()
                if isinstance(a["created"], date) and (first_day - a["created"]).days < 365)
    known_age = sum(1 for a in accounts.values() if isinstance(a["created"], date))
    young_share = young / max(known_age, 1) if known_age else 0.0
    repeat_share = sum(1 for k in accounts if repeat_counts.get(k, 0) >= 2) / max(n_acc, 1)

    if kind == "red":
        score = score_network(n_acc, span, low_share, young_share, repeat_share, med_fol)
    else:   # repetición de una sola cuenta: más repeticiones, más puntaje
        # Menos indicativo que una red de cuentas (puede ser spam o la misma respuesta a varias personas):
        # tope 0,6 para que las redes coordinadas queden siempre por encima en la lista.
        score = round(min(0.2 + 0.05 * (len(members) - MIN_REPEATS + 1), 0.6), 3)
    ents = Counter(m["entity_name"] for m in members).most_common(1)[0]
    ent_id = next(m["entity_id"] for m in members if m["entity_name"] == ents[0])
    return {
        "kind": kind, "score": score, "entity_id": ent_id, "entity_name": ents[0],
        "platform": Counter(m["platform"] for m in members).most_common(1)[0][0],
        "first_seen": ts[0], "last_seen": ts[-1], "accounts_count": n_acc, "mentions_count": len(members),
        "span_hours": round(span, 1), "median_followers": med_fol, "low_follower_share": round(low_share, 3),
        "sentiment_mix": dict(Counter(m["sentiment"] or "sin_clasificar" for m in members)),
        "sample_text": members[0]["content"][:500], "members": members,
    }


def run_detection(db, days: int = 14, max_rows: int = 15000, persist: bool = True) -> dict:
    """Detecta grupos de actividad coordinada y (si persist) los guarda para revisión."""
    from app.models.coordination import CoordinationCluster, CoordinationMember

    docs = _load_documents(db, days, max_rows)
    if not docs:
        return {"documents": 0, "network_clusters": 0, "repetition_clusters": 0}

    # 1) redes: casi-duplicados entre cuentas distintas
    net = [c for c in cluster_documents(docs) if len({docs[i]["author"] for i in c}) >= MIN_ACCOUNTS_NETWORK]
    repeat_counts = Counter()                       # en cuántos grupos aparece cada cuenta
    for c in net:
        for a in {docs[i]["author"] for i in c}:
            repeat_counts[a] += 1
    clusters = [_cluster_metrics(docs, c, "red", repeat_counts) for c in net]

    # 2) repetición: una cuenta con el mismo texto >= 5 veces
    by_author_text = defaultdict(list)
    for i, d in enumerate(docs):
        by_author_text[(d["author"], " ".join(d["toks"]))].append(i)
    for idxs in by_author_text.values():
        if len(idxs) >= MIN_REPEATS:
            clusters.append(_cluster_metrics(docs, idxs, "repeticion", repeat_counts))

    result = {"documents": len(docs), "network_clusters": len(net),
              "repetition_clusters": len(clusters) - len(net)}
    if not persist:
        result["top"] = sorted(clusters, key=lambda c: -c["score"])[:5]
        return result

    # Persistencia: se reconstruyen los grupos "nuevo"; los ya revisados (confirmado/descartado) se conservan
    reviewed_mentions = {
        r[0] for r in db.query(CoordinationMember.mention_id)
        .join(CoordinationCluster, CoordinationCluster.id == CoordinationMember.cluster_id)
        .filter(CoordinationCluster.status != "nuevo").all()
    }
    db.query(CoordinationCluster).filter(CoordinationCluster.status == "nuevo").delete(synchronize_session=False)

    created = skipped = 0
    for c in clusters:
        if any(m["mention_id"] in reviewed_mentions for m in c["members"]):
            skipped += 1
            continue
        row = CoordinationCluster(
            kind=c["kind"], entity_id=c["entity_id"], entity_name=c["entity_name"], platform=c["platform"],
            first_seen=c["first_seen"], last_seen=c["last_seen"], accounts_count=c["accounts_count"],
            mentions_count=c["mentions_count"], span_hours=c["span_hours"], median_followers=c["median_followers"],
            low_follower_share=c["low_follower_share"], score=c["score"], sentiment_mix=c["sentiment_mix"],
            sample_text=c["sample_text"], status="nuevo",
        )
        db.add(row)
        db.flush()
        for m in sorted(c["members"], key=lambda x: x["ts"]):
            db.add(CoordinationMember(
                cluster_id=row.id, mention_id=m["mention_id"], account_profile_id=m["profile_id"],
                author_username=m["username"], author_ext_id=m["author"], followers=m["followers"],
                account_created=m["created"] if isinstance(m["created"], date) else None,
                published_at=m["ts"], sentiment=m["sentiment"], content_preview=m["content"][:600], url=m["url"],
            ))
        created += 1
    db.commit()
    result.update({"created": created, "skipped_reviewed": skipped})
    return result
