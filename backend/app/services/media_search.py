"""
Módulo 8 — Búsqueda Inversa de Imágenes y Videos
=================================================
Dado una imagen o video, encuentra dónde fue publicado (web + BD interna)
y quién lo publicó.

Motores disponibles:
  internal       — pHash en BD de SONAR (siempre disponible, gratis)
  google_vision  — Google Cloud Vision Web Detection (requiere GOOGLE_CLOUD_API_KEY)
  tineye         — TinEye Reverse Image Search (requiere TINEYE_API_KEY)
  bing           — Bing Visual Search (requiere BING_SEARCH_KEY)
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
                    # Verificar que el frame no sea negro (mean < 10)
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


def _search_tineye(img_bytes: bytes) -> list[dict]:
    """TinEye Reverse Image Search."""
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


def _search_bing_visual(img_bytes: bytes) -> list[dict]:
    """Bing Visual Search."""
    key = settings.BING_SEARCH_KEY
    if not key:
        return []
    try:
        r = requests.post(
            "https://api.cognitive.microsoft.com/bing/v7.0/images/visualsearch",
            headers={"Ocp-Apim-Subscription-Key": key},
            files={"image": ("image.jpg", img_bytes, "image/jpeg")},
            timeout=EXTERNAL_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for tag in data.get("tags", []):
            for action in tag.get("actions", []):
                if action.get("actionType") in ("PagesIncluding", "VisualSearch"):
                    for val in (action.get("data", {}).get("value") or [])[:5]:
                        results.append({
                            "engine":    "bing",
                            "url":       val.get("hostPageUrl"),
                            "thumbnail": val.get("thumbnailUrl"),
                            "source":    _domain(val.get("hostPageUrl", "")),
                            "name":      val.get("name"),
                        })
        return results
    except Exception as e:
        logger.warning("[MediaSearch] Bing error: %s", e)
        return []


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


# ── Orquestador público ───────────────────────────────────────

ALL_ENGINES = ("internal", "google_vision", "tineye", "bing")


def search_by_image_bytes(
    db: Session,
    img_bytes: bytes,
    engines: list[str],
) -> dict:
    engines = [e for e in engines if e in ALL_ENGINES]
    if not engines:
        engines = ["internal"]

    phash = _compute_phash(img_bytes)

    results       = {e: [] for e in ALL_ENGINES}
    engines_used  = []
    engines_skipped = []

    _external_keys = {
        "google_vision": settings.GOOGLE_CLOUD_API_KEY,
        "tineye":        settings.TINEYE_API_KEY,
        "bing":          settings.BING_SEARCH_KEY,
    }
    _external_fns = {
        "google_vision": _search_google_vision,
        "tineye":        _search_tineye,
        "bing":          _search_bing_visual,
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
