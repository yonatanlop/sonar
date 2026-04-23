from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.shared.config import settings
from app.shared.deps import get_db, get_current_user, require_admin
from app.modules.monitoring.application.schemas import SocialPlatformOut
from app.modules.monitoring.infrastructure.entity_repository import SqlSocialPlatformRepository
from app.modules.monitoring.infrastructure.orm import SocialPlatformORM

router = APIRouter(prefix="/platforms", tags=["Plataformas"])


class PlatformStatusOut(BaseModel):
    platforms: list[SocialPlatformOut]
    twitter: dict
    instagram: dict
    facebook: dict


def _twitter_status() -> dict:
    db_path = getattr(settings, "TWITTER_ACCOUNTS_DB", "/app/twitter_accounts.db")
    if not os.path.exists(db_path):
        return {"configured": False, "accounts_total": 0, "accounts_active": 0,
                "needs_action": "No hay cuentas configuradas"}
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM accounts")
        total = cur.fetchone()[0]
        try:
            cur.execute("SELECT COUNT(*) FROM accounts WHERE active = 1")
            active = cur.fetchone()[0]
        except Exception:
            active = total
        conn.close()
        return {"configured": total > 0, "accounts_total": total, "accounts_active": active,
                "needs_action": None if active > 0 else "Re-autenticar cuentas"}
    except Exception as exc:
        return {"configured": False, "accounts_total": 0, "accounts_active": 0,
                "needs_action": str(exc)}


def _instagram_status() -> dict:
    user = settings.IG_ACCOUNT_1_USERNAME
    return {
        "configured": bool(user),
        "username": user or None,
        "needs_action": None if user else "Configurar IG_ACCOUNT_1_USERNAME en .env",
    }


def _facebook_status() -> dict:
    cookies = settings.FB_COOKIES_FILE
    configured = bool(cookies) and os.path.exists(cookies)
    return {
        "configured": configured,
        "cookies_file": cookies or None,
        "needs_action": None if configured else "Subir cookies de Facebook",
    }


@router.get("", response_model=PlatformStatusOut)
def get_platform_status(db: Session = Depends(get_db), _=Depends(get_current_user)):
    platforms = [SocialPlatformOut(id=r.id, name=r.name, code=r.code, active=r.active)
                 for r in db.query(SocialPlatformORM).all()]
    return PlatformStatusOut(
        platforms=platforms,
        twitter=_twitter_status(),
        instagram=_instagram_status(),
        facebook=_facebook_status(),
    )


@router.patch("/{platform_id}/toggle", response_model=SocialPlatformOut)
def toggle_platform(platform_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    repo = SqlSocialPlatformRepository(db)
    platforms = repo.list()
    p = next((x for x in platforms if x.id == platform_id), None)
    if not p:
        from app.shared.exceptions import NotFoundError
        raise NotFoundError("Plataforma no encontrada")
    updated = repo.update_status(platform_id, not p.active)
    return SocialPlatformOut(id=updated.id, name=updated.name, code=updated.code, active=updated.active)
