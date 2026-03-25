"""
Sugeridor Automático de Keywords — Módulo 5.2 v2

Analiza las menciones de los últimos 30 días por entidad y extrae
términos frecuentes co-ocurrentes que NO están entre las keywords actuales.
Usa TF-IDF (scikit-learn, ya instalado) sobre el corpus de menciones.

No requiere nueva tabla: las sugerencias se calculan en tiempo real
sobre las menciones existentes. Resultado cacheable en Redis (30 min).
"""
import logging
import re

import numpy as np

logger = logging.getLogger(__name__)

# ── Stopwords ─────────────────────────────────────────────────────

_STOPWORDS = {
    # Español
    "de","la","el","en","y","a","los","del","se","las","un","por","con","no","una","su","al","lo",
    "como","más","pero","sus","le","ya","o","este","si","porque","esta","entre","cuando","muy",
    "sin","sobre","ser","tiene","le","todo","también","hasta","hay","donde","han","quien","están",
    "estado","desde","todo","nos","durante","ni","contra","ese","eso","ante","ellos","e","esto",
    "mi","antes","algunos","qué","unos","yo","otro","otras","otros","otra","él","tanto","esa",
    "estos","mucho","quienes","nada","muchos","cual","poco","ella","estar","estas","algunas",
    "algo","nosotros","mi","mis","tú","te","ti","tu","tus","vosotros","os","vuestro","vuestra",
    "vuestros","vuestras","él","ellos","ella","ellas","me","mío","mía","míos","mías","tuyo",
    "tuya","tuyos","tuyas","suyo","suya","suyos","suyas","nuestro","nuestra","nuestros","nuestras",
    # Inglés
    "the","and","is","in","it","of","to","that","was","he","she","for","on","are","with","as",
    "at","be","by","this","from","or","an","but","not","have","had","they","which","one","you",
    "were","her","all","there","their","what","so","up","out","if","about","who","get","which",
    # Digital/ruido
    "https","http","www","com","rt","via","cc","amp","co","bit","ly","goo","gl","pic","twitter",
    "instagram","facebook","youtube","tiktok","reddit","video","foto","photo","link","share",
    "click","subscribe","follow","like","retweet","comment","share","post","update",
    "hoy","ayer","mañana","ahora","antes","después","horas","hora","minutos","minuto",
    "enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre",
    "noviembre","diciembre","lunes","martes","miércoles","jueves","viernes","sábado","domingo",
}


def _clean(text: str) -> str:
    """Limpia texto: quita URLs, menciones, números puros, colapsa espacios."""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"@\w+",        " ", text)
    text = re.sub(r"#(\w+)",    r" \1 ", text)   # conservar texto del hashtag
    text = re.sub(r"\b\d+\b",     " ", text)     # eliminar números solos
    text = re.sub(r"[^a-záéíóúüñA-ZÁÉÍÓÚÜÑA-Za-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _build_exclusions(entity) -> set[str]:
    """Construye el conjunto de términos a excluir (keywords actuales + nombre + aliases)."""
    excluded = set()

    # Nombre de la entidad (partes individuales)
    for part in entity.name.lower().split():
        if len(part) > 2:
            excluded.add(part)
    excluded.add(entity.name.lower())

    # Keywords existentes
    for kw in (entity.keywords or []):
        if hasattr(kw, "keyword"):
            excluded.add(kw.keyword.lower())

    # Aliases
    for alias in (entity.aliases or []):
        if hasattr(alias, "alias"):
            for part in alias.alias.lower().split():
                if len(part) > 2:
                    excluded.add(part)

    return excluded


def get_keyword_suggestions(db, entity, days: int = 30, top_n: int = 10) -> list[dict]:
    """
    Retorna hasta `top_n` sugerencias de keywords con score de relevancia (0-1).

    Algoritmo:
      1. Corpus: hasta 300 menciones procesadas de los últimos `days` días.
      2. TF-IDF con n-gramas (1,2), min_df=3 (aparece en ≥3 menciones).
      3. Score = media TF-IDF del término en el corpus.
      4. Filtra: stopwords, términos ya en keywords, nombre/aliases de la entidad.
    """
    from datetime import datetime, timedelta, timezone
    from app.models.mention import Mention
    from sklearn.feature_extraction.text import TfidfVectorizer

    since = datetime.now(timezone.utc) - timedelta(days=days)

    mentions = (
        db.query(Mention)
        .filter(
            Mention.entity_id    == entity.id,
            Mention.collected_at >= since,
            Mention.processed    == True,
        )
        .order_by(Mention.urgency_score.desc().nullslast())
        .limit(300)
        .all()
    )

    if len(mentions) < 10:
        return []

    corpus = [_clean(m.content_clean or m.content or "") for m in mentions]
    corpus = [t for t in corpus if len(t) > 15]

    if len(corpus) < 5:
        return []

    excluded = _build_exclusions(entity)

    try:
        vectorizer = TfidfVectorizer(
            max_features=300,
            ngram_range=(1, 2),
            stop_words=list(_STOPWORDS),
            min_df=max(2, len(corpus) // 20),  # aparece al menos en 5% de menciones
            token_pattern=r"[a-záéíóúüña-z]{3,}",  # mínimo 3 caracteres
        )
        X = vectorizer.fit_transform(corpus)
    except Exception as exc:
        logger.warning(f"[KeywordSuggester] TF-IDF falló para {entity.name}: {exc}")
        return []

    feature_names = vectorizer.get_feature_names_out()
    mean_scores   = np.asarray(X.mean(axis=0)).flatten()

    suggestions = []
    for term, score in zip(feature_names, mean_scores):
        if score < 0.001:
            continue
        # Filtro de exclusiones
        if any(term == exc or exc in term or term in exc for exc in excluded):
            continue
        if term in _STOPWORDS:
            continue
        # Normalizar score a 0-1
        suggestions.append({"keyword": term, "score": round(float(score), 4)})

    if not suggestions:
        return []

    # Normalizar al máximo
    max_score = max(s["score"] for s in suggestions) or 1
    for s in suggestions:
        s["relevance"] = round(s["score"] / max_score, 2)

    suggestions.sort(key=lambda x: x["relevance"], reverse=True)
    return suggestions[:top_n]
