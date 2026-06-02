"""
Módulo 8 — Búsqueda Inversa de Imágenes y Videos
API endpoints para buscar dónde fue publicada una imagen o video.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix="/media-search", tags=["Búsqueda Inversa de Imágenes"])

ALL_ENGINES = {"internal", "google_vision", "saucenao", "yandex", "tineye"}


def _parse_engines(engines_str: str) -> list[str]:
    parts = [e.strip() for e in engines_str.split(",") if e.strip()]
    valid = [e for e in parts if e in ALL_ENGINES]
    return valid if valid else ["internal"]


# ── Schemas ───────────────────────────────────────────────────

class ByUrlRequest(BaseModel):
    url: str
    engines: List[str] = ["internal"]


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/by-url")
def search_by_url(
    body: ByUrlRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Busca dónde fue publicada una imagen dada su URL."""
    from app.services.media_search import search_by_image_url
    try:
        return search_by_image_url(db, body.url, body.engines)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/by-upload")
async def search_by_upload(
    file: UploadFile = File(...),
    engines: str = Form("internal"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Busca dónde fue publicada una imagen o video subido directamente."""
    allowed_types = {
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "video/mp4", "video/quicktime", "video/webm", "video/x-msvideo",
    }
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de archivo no soportado: {file.content_type}",
        )

    MAX_UPLOAD = 50 * 1024 * 1024  # 50 MB para videos
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Archivo demasiado grande (máx 50 MB)",
        )

    from app.services.media_search import search_by_upload
    try:
        return search_by_upload(db, data, file.filename or "upload", _parse_engines(engines))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/from-mention/{mention_id}")
def search_from_mention(
    mention_id: uuid.UUID,
    engines: str = Query("internal"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Busca usando la imagen de una mención ya recopilada por SONAR."""
    from app.services.media_search import search_from_mention
    try:
        return search_from_mention(db, str(mention_id), _parse_engines(engines))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/ai-detect")
async def detect_ai_image(
    file: UploadFile = File(None),
    url: str = Form(None),
    _: User = Depends(get_current_user),
):
    """
    Detecta si una imagen fue generada por IA.
    Usa HuggingFace Inference API (gratis con HUGGINGFACE_TOKEN).
    Retorna: {is_ai, confidence, label}
    """
    from app.services.media_search import detect_ai_generated, _download_to_bytes
    if file:
        img_bytes = await file.read(5 * 1024 * 1024)
    elif url:
        img_bytes = _download_to_bytes(url)
        if not img_bytes:
            raise HTTPException(status_code=422, detail="No se pudo descargar la imagen")
    else:
        raise HTTPException(status_code=422, detail="Se requiere 'file' o 'url'")
    try:
        return detect_ai_generated(img_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
