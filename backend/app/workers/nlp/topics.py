"""
Módulo de Topic Modeling — v2

Agrupa las menciones de una entidad en temas usando TF-IDF + K-Means.

Por qué TF-IDF + K-Means en lugar de BERTopic:
  - BERTopic requiere PyTorch (~2 GB en el contenedor Docker)
  - scikit-learn es ~20 MB y ya se instala para otros módulos (bot classifier)
  - Para corpus de 50-500 menciones, TF-IDF es igual de efectivo
  - Funciona offline, sin llamadas a API externas

Algoritmo:
  1. Obtener menciones de los últimos WINDOW_DAYS días para la entidad
  2. Limpiar y tokenizar texto (español + inglés)
  3. TF-IDF vectorization con stopwords bilingüe
  4. K dinámico: min(ceil(sqrt(n_menciones / 5)), MAX_TOPICS)
  5. MiniBatchKMeans para asignar cada mención a un cluster
  6. Etiquetar cada cluster con los top-N términos TF-IDF
  7. Guardar topic_id + topic_label en cada mención (bulk update)

Programación: cada hora, sobre menciones de los últimos 7 días.
Re-etiqueta todas las menciones del período (los clusters cambian al agregar datos).
"""
import logging
import math
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.models.mention import Mention

logger = logging.getLogger(__name__)

WINDOW_DAYS  = 7      # días hacia atrás a analizar
MIN_MENTIONS = 10     # mínimo de menciones para ejecutar clustering
MAX_TOPICS   = 8      # máximo de clusters
TOP_TERMS    = 5      # términos por topic en la etiqueta

# ── Stopwords bilingüe (español + inglés) compactas ───────────────────────
_STOPWORDS = {
    # Español
    "a","al","algo","algunas","algunos","ante","antes","como","con","contra",
    "cual","cuando","de","del","desde","donde","durante","e","el","ella","ellas",
    "ellos","en","entre","era","es","esa","esas","ese","eso","esos","esta","estaba",
    "estado","estamos","estar","este","esto","estos","fue","fueron","ha","han",
    "hasta","hay","he","hecho","her","him","his","http","https","i","if","in",
    "la","las","le","les","lo","los","más","me","mi","mí","mientras","mismo","muy",
    "no","nos","o","otra","otras","otro","otros","para","pero","por","que","qué",
    "quien","quién","se","si","sí","sin","sobre","su","sus","también","tan","te",
    "toda","todas","todo","todos","una","unas","uno","unos","ya","yo",
    # Inglés
    "a","about","after","all","also","an","and","are","as","at","be","been",
    "but","by","can","do","for","from","get","had","has","have","he","her",
    "him","his","how","i","if","in","is","it","its","just","me","more","my",
    "not","of","on","or","our","out","said","she","so","some","than","that",
    "the","their","them","then","there","they","this","to","up","us","was",
    "we","were","what","when","which","who","will","with","you","your",
    # Ruido digital
    "http","https","www","com","rt","via","amp","co","bit","ly","ift","tt",
}


def _clean(text: str) -> str:
    """Elimina URLs, menciones, hashtags y caracteres no alfabéticos."""
    text = re.sub(r"http\S+",       "", text)
    text = re.sub(r"@\w+",          "", text)
    text = re.sub(r"#(\w+)",        r"\1", text)   # conservar la palabra del hashtag
    text = re.sub(r"[^a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _k_for(n: int) -> int:
    """K dinámico: sqrt(n/5) redondeado, entre 2 y MAX_TOPICS."""
    k = max(2, min(math.ceil(math.sqrt(n / 5)), MAX_TOPICS))
    return k


# ── Detector ──────────────────────────────────────────────────────────────

def detect_topics_for_entity(db: Session, entity: Entity) -> dict:
    """
    Ejecuta topic modeling sobre las menciones recientes de la entidad.
    Actualiza topic_id y topic_label en cada mención.
    Retorna resumen con los temas encontrados.
    """
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)

    mentions = (
        db.query(Mention)
        .filter(
            Mention.entity_id    == entity.id,
            Mention.collected_at >= since,
            Mention.is_relevant  == True,
        )
        .order_by(Mention.collected_at.desc())
        .limit(500)   # cap para eficiencia
        .all()
    )

    if len(mentions) < MIN_MENTIONS:
        logger.debug(f"[Topics] {entity.name} — solo {len(mentions)} menciones, saltando.")
        return {"status": "skipped", "reason": "insufficient_mentions", "count": len(mentions)}

    # ── Preparar corpus ────────────────────────────────────────
    texts = [_clean(m.content_clean or m.content or "") for m in mentions]
    # Filtrar menciones con texto vacío tras limpieza
    valid = [(m, t) for m, t in zip(mentions, texts) if len(t.split()) >= 3]

    if len(valid) < MIN_MENTIONS:
        return {"status": "skipped", "reason": "texts_too_short", "count": len(valid)}

    valid_mentions, valid_texts = zip(*valid)

    # ── TF-IDF ────────────────────────────────────────────────
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import MiniBatchKMeans
        import numpy as np
    except ImportError:
        raise RuntimeError("scikit-learn no instalado. Agregar scikit-learn a requirements.txt.")

    vectorizer = TfidfVectorizer(
        max_features=2000,
        min_df=2,           # término debe aparecer en ≥2 docs
        max_df=0.85,        # ignorar términos en >85% de docs (demasiado comunes)
        ngram_range=(1, 2), # unigramas + bigramas
        stop_words=list(_STOPWORDS),
        sublinear_tf=True,
    )

    try:
        X = vectorizer.fit_transform(valid_texts)
    except ValueError as e:
        logger.warning(f"[Topics] {entity.name} — TF-IDF falló: {e}")
        return {"status": "error", "reason": str(e)}

    # ── K-Means ───────────────────────────────────────────────
    k = _k_for(len(valid_mentions))
    # Asegurar k <= número de muestras
    k = min(k, X.shape[0])

    kmeans = MiniBatchKMeans(
        n_clusters=k,
        random_state=42,
        n_init=5,
        max_iter=200,
        batch_size=min(256, len(valid_mentions)),
    )
    labels = kmeans.fit_predict(X)

    # ── Etiquetas por cluster ─────────────────────────────────
    feature_names = np.array(vectorizer.get_feature_names_out())
    topic_labels: dict[int, str] = {}

    for cluster_id in range(k):
        # Centroide del cluster
        centroid = kmeans.cluster_centers_[cluster_id]
        # Top N términos por peso TF-IDF en el centroide
        top_indices = centroid.argsort()[::-1][:TOP_TERMS]
        terms = [feature_names[i] for i in top_indices if centroid[i] > 0]
        topic_labels[cluster_id] = ", ".join(terms) if terms else f"Tema {cluster_id + 1}"

    # ── Guardar en BD ─────────────────────────────────────────
    for mention, cluster_id in zip(valid_mentions, labels):
        mention.topic_id    = int(cluster_id)
        mention.topic_label = topic_labels[int(cluster_id)]

    # Contar menciones por topic
    from collections import Counter
    counts = Counter(int(l) for l in labels)
    topics_summary = [
        {
            "topic_id": tid,
            "label":    topic_labels[tid],
            "count":    counts[tid],
        }
        for tid in sorted(counts, key=lambda x: -counts[x])
    ]

    logger.info(
        f"[Topics] {entity.name} — {len(valid_mentions)} menciones → "
        f"{k} temas: {[t['label'][:30] for t in topics_summary[:3]]}"
    )
    return {"status": "ok", "topics": topics_summary, "mentions_analyzed": len(valid_mentions)}


# ── Orquestador ────────────────────────────────────────────────────────────

def run_topic_detection(db: Session) -> dict:
    """
    Detecta temas para todas las entidades activas.
    Llamado por la tarea Celery cada hora.
    """
    entities = db.query(Entity).filter(Entity.active == True).all()
    total_topics     = 0
    total_mentions   = 0
    errors           = 0

    logger.info(f"[Topics] Iniciando detección sobre {len(entities)} entidades.")

    for entity in entities:
        try:
            result = detect_topics_for_entity(db, entity)
            if result.get("status") == "ok":
                total_topics   += len(result.get("topics", []))
                total_mentions += result.get("mentions_analyzed", 0)
        except Exception as exc:
            logger.error(f"[Topics] Error en entidad {entity.name}: {exc}", exc_info=True)
            errors += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[Topics] Error en commit: {exc}", exc_info=True)
        errors += 1

    summary = {
        "entities_processed": len(entities),
        "total_topics":        total_topics,
        "mentions_labeled":    total_mentions,
        "errors":              errors,
    }
    logger.info(f"[Topics] Completado: {summary}")
    return summary
