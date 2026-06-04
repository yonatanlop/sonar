"""
Módulo 8 — Búsqueda Inversa de Imágenes y Videos
=================================================
Dado una imagen o video, encuentra dónde fue publicado (web + BD interna)
y quién lo publicó.

Motores disponibles:
  internal       — pHash en BD de SONAR (siempre disponible, gratis)
  google_vision  — Google Cloud Vision Web Detection (requiere GOOGLE_CLOUD_API_KEY)
  saucenao       — SauceNAO Reverse Image Search (gratis, 200/día con SAUCENAO_API_KEY)
  yandex         — Yandex Reverse Image vía SerpApi (requiere SERPAPI_KEY, 100/mes gratis)
  tineye         — TinEye Reverse Image Search (requiere TINEYE_API_KEY — plan de pago)

Nota: Bing Visual Search fue retirado el 11 agosto 2025.

Detección de IA:
  detect_ai_generated() — HuggingFace Inference API (usa HUGGINGFACE_TOKEN, gratis)
"""
import base64
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

import requests
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.mention import Mention, SocialPlatform

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES  = 5 * 1024 * 1024   # 5 MB
DOWNLOAD_TIMEOUT = 15                 # segundos
EXTERNAL_TIMEOUT = 20                 # segundos por motor externo
INTERNAL_DAYS    = 180                # ventana de búsqueda interna
INTERNAL_MAX_HAMMING = 10            # distancia máxima (0=idéntica, 64=totalmente diferente)
BATCH_PHASH      = 50                 # menciones por ciclo de cómputo


# ── Helpers ───────────────────────────────────────────────────

def _compute_phash(img_bytes: bytes) -> Optional[str]:
    """Calcula pHash perceptual de una imagen. Retorna string hex o None si falla."""
    try:
        import imagehash
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        return str(imagehash.phash(img))
    except Exception as e:
        logger.debug("[MediaSearch] pHash error: %s", e)
        return None


def _download_to_bytes(url: str) -> Optional[bytes]:
    """Descarga imagen/video desde URL. Retorna bytes o None si falla."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SONAR/2.0; media-search)"}
        r = requests.get(url, headers=headers, timeout=DOWNLOAD_TIMEOUT, stream=True)
        r.raise_for_status()
        data = b""
        for chunk in r.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > MAX_IMAGE_BYTES:
                logger.debug("[MediaSearch] Archivo demasiado grande: %s", url)
                return None
        return data
    except Exception as e:
        logger.debug("[MediaSearch] Download error %s: %s", url, e)
        return None


def _extract_first_useful_frame(video_bytes: bytes, filename: str) -> Optional[bytes]:
    """
    Extrae el primer frame útil de un video.
    Intenta PIL primero (GIF/APNG), luego opencv si está disponible.
    Retorna JPEG bytes o None.
    """
    # PIL: soporta GIF y algunos formatos animados
    try:
        img = Image.open(BytesIO(video_bytes))
        if hasattr(img, "n_frames") and img.n_frames > 0:
            img.seek(0)
            buf = BytesIO()
            img.convert("RGB").save(buf, format="JPEG")
            return buf.getvalue()
    except Exception:
        pass

    # opencv: para MP4/MOV/AVI/WEBM
    try:
        import cv2
        import tempfile, os
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp4"
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name
        try:
            cap = cv2.VideoCapture(tmp_path)
            for ms in (1000, 3000, 0):
                cap.set(cv2.CAP_PROP_POS_MSEC, ms)
                ret, frame = cap.read()
                if ret and frame is not None:
                    import numpy as np
                    if np.mean(frame) > 10:
                        ok, buf = cv2.imencode(".jpg", frame)
                        if ok:
                            cap.release()
                            return buf.tobytes()
            cap.release()
        finally:
            os.unlink(tmp_path)
    except ImportError:
        logger.debug("[MediaSearch] opencv no disponible para extracción de frames")
    except Exception as e:
        logger.debug("[MediaSearch] Frame extraction error: %s", e)

    return None


def _first_media_url(mention: Mention) -> Optional[str]:
    try:
        urls = json.loads(mention.media_urls or "[]")
        return urls[0] if urls else None
    except Exception:
        return None


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


# ── Motor interno ─────────────────────────────────────────────

def _search_internal(db: Session, query_phash: str) -> list[dict]:
    """Busca menciones con imágenes visualmente similares en la BD de SONAR."""
    try:
        import imagehash
        query_hash = imagehash.hex_to_hash(query_phash)
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=INTERNAL_DAYS)

    rows = (
        db.query(Mention, SocialPlatform.code)
        .join(SocialPlatform, Mention.platform_id == SocialPlatform.id)
        .filter(
            Mention.image_phash.isnot(None),
            Mention.collected_at >= cutoff,
        )
        .all()
    )

    results = []
    for mention, platform_code in rows:
        try:
            candidate_hash = imagehash.hex_to_hash(mention.image_phash)
            distance = query_hash - candidate_hash
            if distance <= INTERNAL_MAX_HAMMING:
                results.append({
                    "engine":           "sonar_internal",
                    "mention_id":       str(mention.id),
                    "url":              mention.url,
                    "author":           mention.author_username,
                    "platform":         platform_code,
                    "published_at":     mention.published_at.isoformat() if mention.published_at else None,
                    "thumbnail":        _first_media_url(mention),
                    "hamming_distance": int(distance),
                    "similarity":       round(1 - distance / 64, 3),
                })
        except Exception:
            continue

    results.sort(key=lambda r: r["hamming_distance"])
    return results


# ── Motores externos ──────────────────────────────────────────

def _search_google_vision(img_bytes: bytes) -> list[dict]:
    """Google Cloud Vision Web Detection."""
    key = settings.GOOGLE_CLOUD_API_KEY
    if not key:
        return []
    try:
        encoded = base64.b64encode(img_bytes).decode("utf-8")
        payload = {
            "requests": [{
                "image":    {"content": encoded},
                "features": [{"type": "WEB_DETECTION", "maxResults": 20}],
            }]
        }
        r = requests.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={key}",
            json=payload,
            timeout=EXTERNAL_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        web = data.get("responses", [{}])[0].get("webDetection", {})

        results = []
        for item in web.get("fullMatchingImages", []):
            results.append({
                "engine":    "google_vision",
                "url":       item.get("url"),
                "thumbnail": item.get("url"),
                "source":    _domain(item.get("url", "")),
                "type":      "full_match",
            })
        for item in web.get("pagesWithMatchingImages", []):
            results.append({
                "engine":    "google_vision",
                "url":       item.get("url"),
                "thumbnail": (item.get("fullMatchingImages") or [{}])[0].get("url"),
                "source":    _domain(item.get("url", "")),
                "type":      "page_with_image",
                "title":     item.get("pageTitle"),
            })
        return results
    except Exception as e:
        logger.warning("[MediaSearch] Google Vision error: %s", e)
        return []


def _search_saucenao(img_bytes: bytes) -> list[dict]:
    """
    SauceNAO Reverse Image Search.
    Gratis: 200 búsquedas/día con API key (registro gratuito en saucenao.com).
    Sin key: funciona con límite muy bajo (4 búsquedas/30 seg).
    """
    try:
        params = {"db": 999, "output_type": 2, "numres": 8}
        if settings.SAUCENAO_API_KEY:
            params["api_key"] = settings.SAUCENAO_API_KEY
        r = requests.post(
            "https://saucenao.com/search.php",
            params=params,
            files={"file": ("image.jpg", img_bytes, "image/jpeg")},
            timeout=EXTERNAL_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            header    = item.get("header", {})
            data_item = item.get("data", {})
            similarity = float(header.get("similarity", 0)) / 100
            if similarity < 0.5:
                continue
            ext_urls = data_item.get("ext_urls") or []
            ext_url  = ext_urls[0] if ext_urls else None
            results.append({
                "engine":     "saucenao",
                "url":        ext_url,
                "thumbnail":  header.get("thumbnail"),
                "source":     header.get("index_name", ""),
                "similarity": round(similarity, 3),
                "type":       "full_match" if similarity >= 0.9 else "partial_match",
                "author":     data_item.get("creator") or data_item.get("member_name"),
                "title":      data_item.get("title") or data_item.get("source"),
            })
        results.sort(key=lambda r: r["similarity"], reverse=True)
        return results
    except Exception as e:
        logger.warning("[MediaSearch] SauceNAO error: %s", e)
        return []


def _search_yandex(img_bytes: bytes) -> list[dict]:
    """
    Yandex Reverse Image Search vía SerpApi.
    Requiere SERPAPI_KEY (tier gratis: 100 búsquedas/mes en serpapi.com).
    """
    if not settings.SERPAPI_KEY:
        return []
    try:
        b64 = base64.b64encode(img_bytes).decode()
        r = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine":    "yandex_images",
                "image_url": f"data:image/jpeg;base64,{b64}",
                "api_key":   settings.SERPAPI_KEY,
            },
            timeout=EXTERNAL_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for item in (data.get("image_results") or [])[:10]:
            results.append({
                "engine":    "yandex",
                "url":       item.get("link"),
                "thumbnail": item.get("thumbnail"),
                "source":    _domain(item.get("link", "")),
                "title":     item.get("title"),
                "type":      "page_with_image",
            })
        return results
    except Exception as e:
        logger.warning("[MediaSearch] Yandex error: %s", e)
        return []


def _search_tineye(img_bytes: bytes) -> list[dict]:
    """TinEye Reverse Image Search (plan de pago)."""
    key = settings.TINEYE_API_KEY
    if not key:
        return []
    try:
        r = requests.post(
            "https://api.tineye.com/rest/search/",
            data={"api_key": key},
            files={"image_upload": ("image.jpg", img_bytes, "image/jpeg")},
            timeout=EXTERNAL_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for match in data.get("results", {}).get("matches", []):
            for backlink in (match.get("backlinks") or [])[:3]:
                results.append({
                    "engine":     "tineye",
                    "url":        backlink.get("url"),
                    "thumbnail":  match.get("image_url"),
                    "source":     _domain(backlink.get("url", "")),
                    "first_seen": match.get("added"),
                    "num_copies": data.get("results", {}).get("total_results"),
                })
        return results
    except Exception as e:
        logger.warning("[MediaSearch] TinEye error: %s", e)
        return []


# ── Detección de contenido generado por IA ───────────────────

def detect_ai_generated(img_bytes: bytes) -> dict:
    """
    Detecta si la imagen fue generada por IA usando HuggingFace Inference API.
    Modelos probados en orden (el primero que responda correctamente gana):
      1. Nahrawy/AIorNot      — ~98% precisión, etiquetas FAKE/REAL
      2. umm-maybe/AI-image-detector — fallback, etiquetas artificial/human
    Retorna: {is_ai, confidence, label, model_used}
    """
    token = settings.HUGGINGFACE_TOKEN
    if not token:
        raise ValueError("HUGGINGFACE_TOKEN no configurado. Agrégalo al .env para usar esta función.")

    _models = [
        {
            "url":    "https://router.huggingface.co/hf-inference/models/Nahrawy/AIorNot",
            "name":   "Nahrawy/AIorNot",
            "ai_kw":  ("fake", "ai", "artificial"),
            "real_kw": ("real", "human"),
        },
        {
            "url":    "https://router.huggingface.co/hf-inference/models/umm-maybe/AI-image-detector",
            "name":   "umm-maybe/AI-image-detector",
            "ai_kw":  ("artificial", "ai", "fake"),
            "real_kw": ("human", "real"),
        },
    ]

    last_error = None
    for model in _models:
        try:
            r = requests.post(
                model["url"],
                headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                data=img_bytes,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list) or not data:
                continue

            ai_item   = next((x for x in data if any(k in x.get("label","").lower() for k in model["ai_kw"])),   None)
            real_item = next((x for x in data if any(k in x.get("label","").lower() for k in model["real_kw"])), None)
            ai_score  = ai_item["score"]   if ai_item   else 0.0
            is_ai     = ai_score >= 0.5
            confidence = ai_score if is_ai else (real_item["score"] if real_item else 1 - ai_score)
            return {
                "is_ai":      is_ai,
                "confidence": round(confidence, 3),
                "label":      "Generada por IA" if is_ai else "Imagen real",
                "model_used": model["name"],
            }
        except Exception as e:
            logger.warning("[MediaSearch] AI detection error con %s: %s", model["name"], e)
            last_error = e
            continue

    raise ValueError(f"Todos los modelos de detección fallaron. Último error: {last_error}")


# ── Orquestador público ───────────────────────────────────────

ALL_ENGINES = ("internal", "google_vision", "saucenao", "yandex", "tineye")


def search_by_image_bytes(
    db: Session,
    img_bytes: bytes,
    engines: list[str],
) -> dict:
    engines = [e for e in engines if e in ALL_ENGINES]
    if not engines:
        engines = ["internal"]

    phash = _compute_phash(img_bytes)

    results         = {e: [] for e in ALL_ENGINES}
    engines_used    = []
    engines_skipped = []

    _external_keys = {
        "google_vision": settings.GOOGLE_CLOUD_API_KEY,
        "saucenao":      True,   # funciona sin key (límite muy bajo), mejor con key
        "yandex":        settings.SERPAPI_KEY,
        "tineye":        settings.TINEYE_API_KEY,
    }
    _external_fns = {
        "google_vision": _search_google_vision,
        "saucenao":      _search_saucenao,
        "yandex":        _search_yandex,
        "tineye":        _search_tineye,
    }

    for engine in engines:
        if engine == "internal":
            if phash:
                results["internal"] = _search_internal(db, phash)
                engines_used.append("internal")
            else:
                engines_skipped.append("internal")
        else:
            if _external_keys.get(engine):
                results[engine] = _external_fns[engine](img_bytes)
                engines_used.append(engine)
            else:
                engines_skipped.append(engine)

    total = sum(len(v) for v in results.values())
    return {
        "query_phash":      phash,
        "engines_used":     engines_used,
        "engines_skipped":  engines_skipped,
        "results":          results,
        "total_results":    total,
    }


def search_by_image_url(db: Session, url: str, engines: list[str]) -> dict:
    img_bytes = _download_to_bytes(url)
    if not img_bytes:
        raise ValueError(f"No se pudo descargar la imagen: {url}")
    return search_by_image_bytes(db, img_bytes, engines)


def search_by_upload(
    db: Session,
    file_bytes: bytes,
    filename: str,
    engines: list[str],
) -> dict:
    video_exts = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext in video_exts:
        img_bytes = _extract_first_useful_frame(file_bytes, filename)
        if not img_bytes:
            raise ValueError(
                "No se pudo extraer frame del video. "
                "Instala opencv-python en el servidor para soporte completo."
            )
    else:
        img_bytes = file_bytes
    return search_by_image_bytes(db, img_bytes, engines)


def search_from_mention(db: Session, mention_id: str, engines: list[str]) -> dict:
    mention = db.query(Mention).filter(Mention.id == mention_id).first()
    if not mention:
        raise ValueError("Mención no encontrada")
    url = _first_media_url(mention)
    if not url:
        raise ValueError("Esta mención no tiene imágenes adjuntas")
    return search_by_image_url(db, url, engines)


# ── Task helper: cómputo de pHash en lotes ───────────────────

def run_phash_computation(db: Session) -> dict:
    """
    Calcula y guarda image_phash para menciones con media_urls que aún no tienen pHash.
    Procesa un lote de BATCH_PHASH menciones por ejecución.
    """
    rows = (
        db.query(Mention)
        .filter(
            Mention.media_urls.isnot(None),
            Mention.image_phash.is_(None),
        )
        .order_by(Mention.collected_at.desc())
        .limit(BATCH_PHASH)
        .all()
    )

    computed = 0
    failed   = 0
    for mention in rows:
        url = _first_media_url(mention)
        if not url:
            mention.image_phash = ""   # marcamos para no reintentar
            continue
        img_bytes = _download_to_bytes(url)
        if not img_bytes:
            failed += 1
            continue
        phash = _compute_phash(img_bytes)
        if phash:
            mention.image_phash = phash
            computed += 1
        else:
            failed += 1

    db.commit()
    logger.info("[pHash] Computed=%d failed=%d", computed, failed)
    return {"computed": computed, "failed": failed, "batch": len(rows)}
