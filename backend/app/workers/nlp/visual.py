"""
Módulo 7 — Reconocimiento Visual de Personas
=============================================
Detecta rostros de figuras monitoreadas (senadores, líderes religiosos, etc.)
en imágenes adjuntas a menciones de Twitter, YouTube y noticias RSS.

Tecnología: face_recognition (dlib/ArcFace) — 100% local, $0, sin APIs externas.

Estructura de fotos de referencia:
    /app/storage/faces/
        {entity_id}/
            Ana Paola Agudelo/
                foto1.jpg
                foto2.jpg
            Carlos Guevara/
                foto1.jpg
            Manuel Virguez/
                foto1.jpg

Agregar fotos:
    docker compose exec backend python scripts/add_face_reference.py \\
        --entity-id <UUID> --person "Ana Paola Agudelo" --photo-url https://...

Configuración en .env:
    FACE_RECOGNITION_ENABLED=true
    FACE_DISTANCE_THRESHOLD=0.55   # menor = más estricto (0.4–0.6 recomendado)
"""
import json
import logging
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.mention import Mention

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB
DOWNLOAD_TIMEOUT    = 10                  # segundos
MAX_IMAGES_PER_MENTION = 3               # máx imágenes a analizar por mención
BATCH_SIZE = 15                          # menciones por ejecución del task


# ── Cache de encodings de referencia ─────────────────────────
# Cargados una vez por proceso worker; se invalida si cambian los archivos.
_ref_cache: dict[str, list[tuple[str, object]]] = {}


def _load_reference_encodings(entity_id: str) -> list[tuple[str, object]]:
    """
    Carga y devuelve lista de (nombre_persona, face_encoding) para la entidad.
    Usa caché en memoria para no releer disco en cada mención.
    """
    import face_recognition

    if entity_id in _ref_cache:
        return _ref_cache[entity_id]

    faces_dir = Path(settings.FACES_DIR) / entity_id
    if not faces_dir.exists():
        _ref_cache[entity_id] = []
        return []

    encodings: list[tuple[str, object]] = []

    for person_dir in sorted(faces_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        person_name = person_dir.name

        for img_path in person_dir.iterdir():
            if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            try:
                img = face_recognition.load_image_file(str(img_path))
                encs = face_recognition.face_encodings(img)
                if encs:
                    encodings.append((person_name, encs[0]))
                    logger.debug(f"[Visual] Referencia cargada: {person_name} ({img_path.name})")
                else:
                    logger.warning(f"[Visual] No se detectó rostro en referencia: {img_path}")
            except Exception as exc:
                logger.warning(f"[Visual] Error cargando referencia {img_path}: {exc}")

    _ref_cache[entity_id] = encodings
    logger.info(f"[Visual] {len(encodings)} encodings de referencia para entidad {entity_id}")
    return encodings


def invalidate_cache(entity_id: str) -> None:
    """Limpia el caché de encodings de una entidad (llamar tras agregar nuevas fotos)."""
    _ref_cache.pop(entity_id, None)


def _download_image(url: str) -> Optional[object]:
    """
    Descarga una imagen desde URL y la devuelve como array numpy.
    Retorna None si falla o excede el tamaño máximo.
    """
    import requests
    import face_recognition
    import numpy as np
    from PIL import Image

    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        resp.raise_for_status()

        # Verificar tamaño antes de descargar todo
        content_length = int(resp.headers.get("content-length", 0))
        if content_length > MAX_IMAGE_SIZE_BYTES:
            logger.debug(f"[Visual] Imagen muy grande ({content_length} bytes), omitida: {url}")
            return None

        data = b""
        for chunk in resp.iter_content(chunk_size=8192):
            data += chunk
            if len(data) > MAX_IMAGE_SIZE_BYTES:
                logger.debug(f"[Visual] Imagen superó 5MB en descarga, omitida: {url}")
                return None

        # Convertir a array RGB que face_recognition pueda procesar
        pil_img = Image.open(BytesIO(data)).convert("RGB")
        return np.array(pil_img)

    except Exception as exc:
        logger.debug(f"[Visual] Error descargando imagen {url}: {exc}")
        return None


def analyze_mention(db: Session, mention: Mention) -> bool:
    """
    Analiza las imágenes de una mención y marca visual_match si detecta
    alguna persona de referencia de la entidad.

    Retorna True si encontró al menos una coincidencia.
    """
    import face_recognition as fr

    if not mention.media_urls:
        mention.visual_match = False
        return False

    try:
        urls = json.loads(mention.media_urls)
    except (json.JSONDecodeError, TypeError):
        mention.visual_match = False
        return False

    if not urls:
        mention.visual_match = False
        return False

    reference_encodings = _load_reference_encodings(str(mention.entity_id))
    if not reference_encodings:
        # Sin fotos de referencia para esta entidad — marcar como analizado sin match
        mention.visual_match = False
        return False

    matched_names: set[str] = set()
    threshold = settings.FACE_DISTANCE_THRESHOLD

    for url in urls[:MAX_IMAGES_PER_MENTION]:
        img_array = _download_image(url)
        if img_array is None:
            continue

        try:
            face_encodings = fr.face_encodings(img_array)
        except Exception as exc:
            logger.debug(f"[Visual] Error extrayendo encodings de {url}: {exc}")
            continue

        for face_enc in face_encodings:
            known_encs = [enc for _, enc in reference_encodings]
            known_names = [name for name, _ in reference_encodings]

            distances = fr.face_distance(known_encs, face_enc)
            for dist, name in zip(distances, known_names):
                if dist <= threshold:
                    matched_names.add(name)
                    logger.info(
                        f"[Visual] Coincidencia: {name} "
                        f"(dist={dist:.3f}) en mención {mention.id}"
                    )

        time.sleep(0.1)  # pequeña pausa entre imágenes

    if matched_names:
        mention.visual_match = True
        mention.visual_match_names = json.dumps(sorted(matched_names))
    else:
        mention.visual_match = False
        mention.visual_match_names = None

    return bool(matched_names)


def run_visual_analysis(db: Session) -> dict:
    """
    Procesa un batch de menciones pendientes de análisis visual.
    Una mención está pendiente si tiene media_urls y visual_match IS NULL.
    """
    if not settings.FACE_RECOGNITION_ENABLED:
        return {"status": "disabled", "processed": 0}

    pending = (
        db.query(Mention)
        .filter(
            Mention.media_urls.isnot(None),
            Mention.visual_match.is_(None),
        )
        .limit(BATCH_SIZE)
        .all()
    )

    if not pending:
        return {"status": "ok", "processed": 0, "matches": 0}

    processed = 0
    matches = 0

    for mention in pending:
        try:
            found = analyze_mention(db, mention)
            if found:
                matches += 1
            processed += 1
        except Exception as exc:
            logger.error(f"[Visual] Error analizando mención {mention.id}: {exc}")
            mention.visual_match = False  # marcar para no reintentar

    db.commit()
    logger.info(f"[Visual] {processed} menciones analizadas, {matches} con coincidencia visual")
    return {"status": "ok", "processed": processed, "matches": matches}


# ── Gestión de fotos de referencia (usada por el script CLI) ──

def add_face_reference(entity_id: str, person_name: str, image_source: str) -> bool:
    """
    Agrega una foto de referencia para una persona de la entidad.
    image_source puede ser una URL o una ruta local.
    Retorna True si se guardó correctamente y se detectó un rostro.
    """
    import face_recognition
    import numpy as np
    from PIL import Image

    dest_dir = Path(settings.FACES_DIR) / entity_id / person_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Determinar índice para el nombre del archivo
    existing = list(dest_dir.glob("*.jpg")) + list(dest_dir.glob("*.png"))
    idx = len(existing) + 1
    dest_path = dest_dir / f"foto{idx}.jpg"

    # Cargar imagen
    try:
        if image_source.startswith("http://") or image_source.startswith("https://"):
            img_array = _download_image(image_source)
            if img_array is None:
                logger.error(f"[Visual] No se pudo descargar imagen: {image_source}")
                return False
            pil_img = Image.fromarray(img_array)
        else:
            pil_img = Image.open(image_source).convert("RGB")
            img_array = np.array(pil_img)
    except Exception as exc:
        logger.error(f"[Visual] Error cargando imagen: {exc}")
        return False

    # Verificar que hay al menos un rostro detectable
    try:
        encs = face_recognition.face_encodings(img_array)
        if not encs:
            logger.error(f"[Visual] No se detectó ningún rostro en la imagen proporcionada.")
            return False
    except Exception as exc:
        logger.error(f"[Visual] Error al detectar rostros: {exc}")
        return False

    # Guardar imagen
    pil_img.save(str(dest_path), "JPEG", quality=90)
    invalidate_cache(entity_id)
    logger.info(f"[Visual] Referencia guardada: {dest_path}")
    return True


def list_face_references(entity_id: str) -> list[dict]:
    """Lista las personas y cantidad de fotos de referencia para la entidad."""
    faces_dir = Path(settings.FACES_DIR) / entity_id
    if not faces_dir.exists():
        return []

    result = []
    for person_dir in sorted(faces_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        photos = [
            p for p in person_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        ]
        result.append({
            "person_name": person_dir.name,
            "photo_count": len(photos),
        })
    return result


def delete_face_reference(entity_id: str, person_name: str) -> bool:
    """Elimina todas las fotos de referencia de una persona para la entidad."""
    import shutil
    person_dir = Path(settings.FACES_DIR) / entity_id / person_name
    if not person_dir.exists():
        return False
    shutil.rmtree(person_dir)
    invalidate_cache(entity_id)
    return True
