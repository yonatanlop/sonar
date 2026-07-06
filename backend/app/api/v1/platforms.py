import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.database import get_db
from app.models.mention import FacebookAccount, InstagramAccount, Mention, SocialPlatform

router = APIRouter(prefix="/platforms", tags=["Plataformas"])


# ── Helpers de estado por plataforma ──────────────────────────────────────

def _twitter_status() -> dict:
    """Verifica cuentas activas en el pool de twscrape."""
    db_path = settings.TWITTER_ACCOUNTS_DB
    if not os.path.exists(db_path):
        return {"configured": False, "accounts_total": 0, "accounts_active": 0,
                "needs_action": "No hay cuentas configuradas. Ejecuta: docker compose exec backend python scripts/add_twitter_account.py"}

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur  = conn.cursor()

        # twscrape guarda las cuentas en la tabla 'accounts'
        cur.execute("SELECT COUNT(*) FROM accounts")
        total = cur.fetchone()[0]

        # Intentar contar cuentas activas (active=1 o sin bloqueo)
        try:
            cur.execute("SELECT COUNT(*) FROM accounts WHERE active = 1")
            active = cur.fetchone()[0]
        except Exception:
            active = total  # versiones antiguas de twscrape no tienen columna active

        conn.close()

        if total == 0:
            return {"configured": False, "accounts_total": 0, "accounts_active": 0,
                    "needs_action": "No hay cuentas configuradas. Ejecuta: docker compose exec backend python scripts/add_twitter_account.py"}

        if active == 0:
            return {"configured": True, "accounts_total": total, "accounts_active": 0,
                    "needs_action": f"Hay {total} cuenta(s) pero ninguna está activa. Puede ser necesario re-autenticar con cookies."}

        return {"configured": True, "accounts_total": total, "accounts_active": active, "needs_action": None}

    except Exception as exc:
        return {"configured": False, "accounts_total": 0, "accounts_active": 0,
                "needs_action": f"Error al leer el pool de cuentas: {exc}"}


def _platform_stats(db: Session, platform_code: str) -> dict:
    """Cuenta menciones recientes y obtiene la última recolectada."""
    platform = db.query(SocialPlatform).filter(SocialPlatform.code == platform_code).first()
    if not platform:
        return {"mentions_24h": 0, "mentions_7d": 0, "last_mention_at": None}

    now     = datetime.now(timezone.utc)
    since1d = now - timedelta(hours=24)
    since7d = now - timedelta(days=7)

    m24 = db.query(func.count(Mention.id)).filter(
        Mention.platform_id  == platform.id,
        Mention.collected_at >= since1d,
    ).scalar() or 0

    m7d = db.query(func.count(Mention.id)).filter(
        Mention.platform_id  == platform.id,
        Mention.collected_at >= since7d,
    ).scalar() or 0

    last = db.query(Mention.collected_at).filter(
        Mention.platform_id == platform.id,
    ).order_by(Mention.collected_at.desc()).first()

    return {
        "mentions_24h":    m24,
        "mentions_7d":     m7d,
        "last_mention_at": last[0].isoformat() if last else None,
    }


def _health_status(configured: bool, mentions_24h: int, last_mention_at: str | None) -> str:
    """
    ok       → configurado + menciones recientes
    warning  → configurado pero sin menciones en 24h (puede ser normal si hay pocas keywords)
    error    → no configurado
    """
    if not configured:
        return "error"
    if mentions_24h > 0:
        return "ok"
    return "warning"


def _instagram_status(db: Session) -> dict:
    """Verifica cuentas activas en la tabla instagram_accounts."""
    accounts = db.query(InstagramAccount).all()
    active   = [a for a in accounts if a.active]
    configured = len(accounts) > 0
    if not configured:
        needs_action = "Agrega al menos una cuenta de Instagram con usuario y contraseña."
    elif not active:
        needs_action = f"Hay {len(accounts)} cuenta(s) pero ninguna está activa."
    else:
        needs_action = None
    return {
        "configured":      configured,
        "accounts_total":  len(accounts),
        "accounts_active": len(active),
        "needs_action":    needs_action,
    }


def _facebook_status(db: Session | None = None) -> dict:
    """
    Estado de Facebook: prioriza el pool de cuentas en DB (facebook_accounts);
    si no hay cuentas, cae al archivo único fb_cookies.json (compat).
    """
    accounts_total = 0
    accounts_active = 0
    if db is not None:
        try:
            accounts = db.query(FacebookAccount).all()
            accounts_total = len(accounts)
            accounts_active = len([a for a in accounts if a.active])
        except Exception:
            accounts_total = accounts_active = 0

    if accounts_total > 0:
        return {
            "configured":     accounts_active > 0,
            "accounts_total": accounts_total,
            "accounts_active": accounts_active,
            "updated_at":     None,
            "needs_action":   None if accounts_active > 0 else "Tienes cuentas pero ninguna activa. Activa al menos una.",
        }

    # Fallback: archivo único
    path = settings.FB_COOKIES_FILE
    configured = os.path.exists(path)
    updated_at = None
    if configured:
        mtime = os.path.getmtime(path)
        updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return {
        "configured":     configured,
        "accounts_total": 1 if configured else 0,
        "accounts_active": 1 if configured else 0,
        "updated_at":     updated_at,
        "needs_action":   None if configured else "Agrega una cuenta de Facebook con sus cookies en la sección Plataformas.",
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
def list_platforms(db: Session = Depends(get_db), _=Depends(get_current_user)):
    platforms = db.query(SocialPlatform).filter(SocialPlatform.active == True).all()
    return [{"id": p.id, "name": p.name, "code": p.code} for p in platforms]


@router.get("/status")
def platforms_status(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    Estado detallado de cada plataforma de scraping:
    - Si está configurada (credenciales presentes)
    - Menciones recolectadas en las últimas 24h y 7 días
    - Última mención recolectada
    - Información de cuentas (Twitter)
    - Acción requerida si hay algún problema
    """
    result = []

    # ── Twitter / X ───────────────────────────────────────────────────────
    tw       = _twitter_status()
    tw_stats = _platform_stats(db, "twitter")
    bearer_configured = bool(settings.TWITTER_BEARER_TOKEN)
    # Plataforma configurada si hay Bearer Token O cuentas twscrape activas
    tw_configured = tw["configured"] or bearer_configured
    needs_action = tw["needs_action"]
    if tw_configured and not bearer_configured:
        needs_action = (needs_action or "") + (" Añade TWITTER_BEARER_TOKEN en .env para mayor fiabilidad (tier 2)." if needs_action else "Añade TWITTER_BEARER_TOKEN en .env para mayor fiabilidad (tier 2).")
    if not tw_configured:
        needs_action = "Configura TWITTER_BEARER_TOKEN en .env (developer.twitter.com) o agrega una cuenta con cookies."
    result.append({
        "code":                "twitter",
        "name":                "Twitter / X",
        "icon":                "🐦",
        "frequency":           "cada 20 min",
        "configured":          tw_configured,
        "status":              _health_status(tw_configured, tw_stats["mentions_24h"], tw_stats["last_mention_at"]),
        "accounts_total":      tw["accounts_total"],
        "accounts_active":     tw["accounts_active"],
        "bearer_configured":   bearer_configured,
        "needs_action":        needs_action,
        "setup_hint":          "Tier 1: cuenta con cookies (twscrape). Tier 2: Bearer Token API v2 (recomendado). Tier 3: Nitter (fallback).",
        **tw_stats,
    })

    # ── YouTube ──────────────────────────────────────────────────────────
    yt_configured = bool(settings.YOUTUBE_API_KEY)
    yt_stats      = _platform_stats(db, "youtube")
    result.append({
        "code":         "youtube",
        "name":         "YouTube",
        "icon":         "▶️",
        "frequency":    "cada 30 min",
        "configured":   yt_configured,
        "status":       _health_status(yt_configured, yt_stats["mentions_24h"], yt_stats["last_mention_at"]),
        "needs_action": None if yt_configured else "Configura YOUTUBE_API_KEY en .env (Google Cloud Console → YouTube Data API v3)",
        "setup_hint":   "Gratuito hasta 10,000 unidades/día. Obtén la clave en console.cloud.google.com",
        **yt_stats,
    })

    # ── Instagram ────────────────────────────────────────────────────────
    ig     = _instagram_status(db)
    ig_stats = _platform_stats(db, "instagram")
    result.append({
        "code":            "instagram",
        "name":            "Instagram",
        "icon":            "📸",
        "frequency":       "cada 30 min",
        "configured":      ig["configured"],
        "status":          _health_status(ig["configured"], ig_stats["mentions_24h"], ig_stats["last_mention_at"]),
        "accounts_total":  ig["accounts_total"],
        "accounts_active": ig["accounts_active"],
        "needs_action":    ig["needs_action"],
        "setup_hint":      "Agrega cuentas de Instagram para buscar posts por hashtag.",
        **ig_stats,
    })

    # ── Facebook ─────────────────────────────────────────────────────────
    fb       = _facebook_status(db)
    fb_stats = _platform_stats(db, "facebook")
    result.append({
        "code":         "facebook",
        "name":         "Facebook",
        "icon":         "📘",
        "frequency":    "cada hora",
        "configured":   fb["configured"],
        "status":       _health_status(fb["configured"], fb_stats["mentions_24h"], fb_stats["last_mention_at"]),
        "accounts_total":  fb["accounts_total"],
        "accounts_active": fb["accounts_active"],
        "cookies_updated_at": fb["updated_at"],
        "needs_action": fb["needs_action"],
        "setup_hint":   "Agrega varias cuentas con sus cookies (Cookie-Editor → Export → JSON). El worker rota entre ellas.",
        **fb_stats,
    })

    # ── RSS / Noticias ────────────────────────────────────────────────────
    rss_stats = _platform_stats(db, "rss")
    result.append({
        "code":         "rss",
        "name":         "RSS / Noticias",
        "icon":         "📰",
        "frequency":    "cada 20 min",
        "configured":   True,   # RSS no necesita credenciales
        "status":       _health_status(True, rss_stats["mentions_24h"], rss_stats["last_mention_at"]),
        "needs_action": None,
        "setup_hint":   "Funciona sin configuración. Lee portales de noticias preconfigurados en español e inglés.",
        **rss_stats,
    })

    return result


# ── Gestión de cuentas Twitter ─────────────────────────────────────────────

class TwitterAccountIn(BaseModel):
    username:       str
    email:          str
    password:       str
    email_password: str = ""   # si vacío se usa password
    cookies_json:   str = ""   # JSON exportado desde Cookie-Editor


class TwitterAccountUpdate(BaseModel):
    cookies_json: str = ""     # nuevo JSON de cookies
    password:     str = ""     # nueva contraseña (opcional)


def _sqlite_accounts() -> list[dict]:
    """Lee todas las cuentas del pool con diagnóstico de estado."""
    db_path = settings.TWITTER_ACCOUNTS_DB
    if not os.path.exists(db_path):
        return []
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("SELECT username, email, active, cookies, error_msg, locks, stats, last_used FROM accounts")
        rows = cur.fetchall()
    except Exception:
        rows = []
    conn.close()

    now = datetime.now(timezone.utc)
    result = []
    for r in rows:
        active    = bool(r["active"])
        error_msg = r["error_msg"] or ""
        last_used = r["last_used"] or ""

        try:
            locks = json.loads(r["locks"] or "{}")
        except Exception:
            locks = {}
        try:
            stats = json.loads(r["stats"] or "{}")
        except Exception:
            stats = {}

        # Determinar cooldown: hay lock en el futuro
        cooldown_until = None
        for lock_time_str in locks.values():
            try:
                lt = datetime.fromisoformat(lock_time_str).replace(tzinfo=timezone.utc)
                if lt > now:
                    cooldown_until = lock_time_str
            except Exception:
                pass

        # Clasificar estado y razón
        if active and not cooldown_until:
            status = "activa"
            reason = "Operando normalmente"
            can_reactivate = False
        elif active and cooldown_until:
            status = "cooldown"
            reason = f"Rate-limit temporal — disponible aprox. {cooldown_until[:16]} UTC"
            can_reactivate = False
        elif not active and ("authenticate" in error_msg.lower() or "(32)" in error_msg or "(135)" in error_msg or "(326)" in error_msg):
            status = "error_auth"
            reason = "Credenciales inválidas o sesión revocada — actualiza cookies o contraseña"
            can_reactivate = True
        elif not active and error_msg:
            status = "error"
            reason = f"Error de Twitter: {error_msg}"
            can_reactivate = True
        else:
            status = "inactiva"
            reason = "Sesión expirada o cuenta posiblemente suspendida por Twitter"
            can_reactivate = True

        result.append({
            "username":        r["username"],
            "email":           r["email"],
            "active":          active,
            "status":          status,
            "reason":          reason,
            "can_reactivate":  can_reactivate,
            "error_msg":       error_msg or None,
            "cooldown_until":  cooldown_until,
            "requests_total":  stats.get("SearchTimeline", 0),
            "last_used":       last_used[:19] if last_used else None,
            "has_cookies":     bool(r["cookies"]),
        })
    return result


async def _twscrape_add(username, email, password, email_password, cookies_str):
    from twscrape import API
    api = API(settings.TWITTER_ACCOUNTS_DB)
    kwargs = dict(username=username, email=email, password=password,
                  email_password=email_password or password)
    if cookies_str:
        kwargs["cookies"] = cookies_str
    try:
        await api.pool.add_account(**kwargs)
    except Exception as e:
        if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
            raise
    # Si se agregó con contraseña (sin cookies) hacer login para activar
    if not cookies_str:
        await api.pool.login_all()


def _sqlite_set_active(username: str, active: int) -> None:
    """Actualiza directamente la columna active en SQLite."""
    import sqlite3
    conn = sqlite3.connect(settings.TWITTER_ACCOUNTS_DB)
    conn.execute("UPDATE accounts SET active = ? WHERE lower(username) = lower(?)",
                 (active, username))
    conn.commit()
    conn.close()


def _sqlite_delete(username: str) -> int:
    """Elimina la cuenta del pool. Retorna filas afectadas."""
    import sqlite3
    conn = sqlite3.connect(settings.TWITTER_ACCOUNTS_DB)
    cur = conn.execute("DELETE FROM accounts WHERE lower(username) = lower(?)", (username,))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected


@router.get("/twitter/accounts")
def list_twitter_accounts(_=Depends(require_admin)):
    """Lista todas las cuentas en el pool de twscrape (solo admin)."""
    return _sqlite_accounts()


@router.post("/twitter/accounts", status_code=201)
def add_twitter_account(body: TwitterAccountIn, _=Depends(require_admin)):
    """
    Agrega (o actualiza) una cuenta al pool de twscrape.
    - Si se provee cookies_json se usa modo cookies (recomendado).
    - Si no, se usa usuario/contraseña e intenta login inmediato.
    """
    cookies_str = None
    if body.cookies_json.strip():
        try:
            json.loads(body.cookies_json)   # validar JSON
            cookies_str = body.cookies_json.strip()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400,
                                detail="cookies_json no es JSON válido. Exporta con Cookie-Editor → 'Export as JSON'.")

    try:
        asyncio.run(_twscrape_add(
            username=body.username.lstrip("@"),
            email=body.email,
            password=body.password,
            email_password=body.email_password,
            cookies_str=cookies_str,
        ))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al agregar cuenta: {exc}")

    # Si se usaron cookies, activar manualmente (twscrape deja active=0 por defecto)
    if cookies_str:
        try:
            _sqlite_set_active(body.username.lstrip("@"), 1)
        except Exception:
            pass   # no crítico

    return {"ok": True, "accounts": _sqlite_accounts()}


@router.post("/twitter/accounts/{username}/activate")
def activate_twitter_account(username: str, _=Depends(require_admin)):
    """Marca la cuenta como activa (útil tras agregar con cookies)."""
    if not os.path.exists(settings.TWITTER_ACCOUNTS_DB):
        raise HTTPException(status_code=404, detail="No hay base de datos de cuentas.")
    _sqlite_set_active(username, 1)
    return {"ok": True, "accounts": _sqlite_accounts()}


@router.post("/twitter/accounts/{username}/reactivate")
def reactivate_twitter_account(username: str, _=Depends(require_admin)):
    """
    Intenta reactivar una cuenta inactiva: limpia error_msg y locks,
    y la marca como activa. Si Twitter la rechaza volverá a quedar
    inactiva con el error actualizado en el próximo uso.
    """
    if not os.path.exists(settings.TWITTER_ACCOUNTS_DB):
        raise HTTPException(status_code=404, detail="No hay base de datos de cuentas.")
    import sqlite3
    conn = sqlite3.connect(settings.TWITTER_ACCOUNTS_DB)
    cur = conn.execute(
        "SELECT username FROM accounts WHERE lower(username) = lower(?)", (username,)
    )
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    conn.execute(
        "UPDATE accounts SET active=1, error_msg=NULL, locks='{}' WHERE lower(username)=lower(?)",
        (username,),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "accounts": _sqlite_accounts()}


@router.put("/twitter/accounts/{username}")
def update_twitter_account(username: str, body: TwitterAccountUpdate, _=Depends(require_admin)):
    """
    Actualiza cookies y/o contraseña de una cuenta existente.
    También reactiva la cuenta (active=1) al guardar.
    """
    if not os.path.exists(settings.TWITTER_ACCOUNTS_DB):
        raise HTTPException(status_code=404, detail="No hay base de datos de cuentas.")

    import sqlite3

    cookies_str = None
    if body.cookies_json.strip():
        try:
            json.loads(body.cookies_json)
            cookies_str = body.cookies_json.strip()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400,
                                detail="cookies_json no es JSON válido. Exporta con Cookie-Editor → 'Export as JSON'.")

    conn = sqlite3.connect(settings.TWITTER_ACCOUNTS_DB)
    try:
        if cookies_str and body.password:
            conn.execute(
                "UPDATE accounts SET cookies = ?, password = ?, active = 1 WHERE lower(username) = lower(?)",
                (cookies_str, body.password, username),
            )
        elif cookies_str:
            conn.execute(
                "UPDATE accounts SET cookies = ?, active = 1 WHERE lower(username) = lower(?)",
                (cookies_str, username),
            )
        elif body.password:
            conn.execute(
                "UPDATE accounts SET password = ?, active = 1 WHERE lower(username) = lower(?)",
                (body.password, username),
            )
        else:
            raise HTTPException(status_code=400, detail="Debes proporcionar cookies_json o password.")
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "accounts": _sqlite_accounts()}


@router.delete("/twitter/accounts/{username}")
def delete_twitter_account(username: str, _=Depends(require_admin)):
    """Elimina una cuenta del pool (solo admin)."""
    if not os.path.exists(settings.TWITTER_ACCOUNTS_DB):
        raise HTTPException(status_code=404, detail="No hay base de datos de cuentas.")
    affected = _sqlite_delete(username)
    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Cuenta @{username} no encontrada.")
    return {"ok": True, "accounts": _sqlite_accounts()}


# ── Gestión de cuentas Instagram ───────────────────────────────────────────

class InstagramAccountIn(BaseModel):
    username: str
    password: str


def _ig_accounts_list(db: Session) -> list[dict]:
    accounts = db.query(InstagramAccount).order_by(InstagramAccount.created_at).all()
    return [{"username": a.username, "active": a.active, "created_at": a.created_at.isoformat()} for a in accounts]


@router.get("/instagram/accounts")
def list_instagram_accounts(db: Session = Depends(get_db), _=Depends(require_admin)):
    return _ig_accounts_list(db)


@router.post("/instagram/accounts", status_code=201)
def add_instagram_account(body: InstagramAccountIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    username = body.username.lstrip("@").strip()
    existing = db.query(InstagramAccount).filter(InstagramAccount.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"La cuenta @{username} ya existe.")
    account = InstagramAccount(username=username, password=body.password, active=True)
    db.add(account)
    db.commit()
    return {"ok": True, "accounts": _ig_accounts_list(db)}


@router.post("/instagram/accounts/{username}/toggle")
def toggle_instagram_account(username: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    account = db.query(InstagramAccount).filter(InstagramAccount.username == username).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Cuenta @{username} no encontrada.")
    account.active = not account.active
    db.commit()
    return {"ok": True, "accounts": _ig_accounts_list(db)}


@router.delete("/instagram/accounts/{username}")
def delete_instagram_account(username: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    account = db.query(InstagramAccount).filter(InstagramAccount.username == username).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Cuenta @{username} no encontrada.")
    db.delete(account)
    db.commit()
    return {"ok": True, "accounts": _ig_accounts_list(db)}


# ── Gestión de cookies Facebook ────────────────────────────────────────────

class FacebookCookiesIn(BaseModel):
    cookies_json: str


@router.get("/facebook/cookies")
def get_facebook_cookies(_=Depends(require_admin)):
    fb = _facebook_status()
    return {"configured": fb["configured"], "updated_at": fb["updated_at"]}


@router.post("/facebook/cookies")
def save_facebook_cookies(body: FacebookCookiesIn, _=Depends(require_admin)):
    try:
        parsed = json.loads(body.cookies_json)
        if not isinstance(parsed, (list, dict)):
            raise ValueError("El JSON debe ser un array u objeto de cookies.")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"JSON de cookies inválido: {exc}")

    path = settings.FB_COOKIES_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el archivo: {exc}")

    return {"ok": True, **_facebook_status()}


@router.delete("/facebook/cookies")
def delete_facebook_cookies(_=Depends(require_admin)):
    path = settings.FB_COOKIES_FILE
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No hay cookies configuradas.")
    os.remove(path)
    return {"ok": True, "configured": False}


# ── Pool de cuentas Facebook (cookies) ─────────────────────────────────────

class FacebookAccountIn(BaseModel):
    label:        str
    cookies_json: str
    proxy_url:    str = ""     # http://usuario:contraseña@host:puerto (opcional)


class FacebookAccountUpdate(BaseModel):
    label:        str = ""
    cookies_json: str = ""
    proxy_url:    str | None = None   # None = no cambiar · "" = quitar · valor = fijar


def _validate_fb_cookies(cookies_json: str) -> str:
    try:
        parsed = json.loads(cookies_json)
        if not isinstance(parsed, (list, dict)):
            raise ValueError("El JSON debe ser un array u objeto de cookies.")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"JSON de cookies inválido: {exc}")
    return cookies_json.strip()


def _validate_fb_proxy(proxy_url: str) -> str:
    """Valida el proxy URL (si viene). Retorna la cadena limpia o '' si vacío."""
    raw = (proxy_url or "").strip()
    if not raw:
        return ""
    from urllib.parse import urlparse
    test = raw if "://" in raw else "http://" + raw
    if not urlparse(test).hostname:
        raise HTTPException(
            status_code=400,
            detail="proxy_url inválido. Formato: http://usuario:contraseña@host:puerto",
        )
    return raw


def _mask_proxy(url: str | None) -> str | None:
    """Enmascara la contraseña del proxy para exponerlo sin filtrar credenciales."""
    if not url:
        return None
    try:
        from urllib.parse import urlparse
        raw = url if "://" in url else "http://" + url
        p = urlparse(raw)
        scheme = p.scheme or "http"
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        if p.username:
            return f"{scheme}://{p.username}:***@{host}{port}"
        return f"{scheme}://{host}{port}"
    except Exception:
        return "***"


def _fb_accounts_list(db: Session) -> list[dict]:
    rows = db.query(FacebookAccount).order_by(FacebookAccount.created_at).all()
    return [{
        "id":          a.id,
        "label":       a.label,
        "active":      a.active,
        "has_cookies": bool(a.cookies_json),
        "has_proxy":   bool(a.proxy_url),
        "proxy":       _mask_proxy(a.proxy_url),
        "last_used":   a.last_used.isoformat() if a.last_used else None,
        "created_at":  a.created_at.isoformat() if a.created_at else None,
    } for a in rows]


@router.get("/facebook/accounts")
def list_facebook_accounts(db: Session = Depends(get_db), _=Depends(require_admin)):
    return _fb_accounts_list(db)


@router.post("/facebook/accounts", status_code=201)
def add_facebook_account(body: FacebookAccountIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="La etiqueta es obligatoria.")
    cookies = _validate_fb_cookies(body.cookies_json)
    proxy = _validate_fb_proxy(body.proxy_url)
    account = FacebookAccount(
        label=label, cookies_json=cookies, proxy_url=(proxy or None), active=True,
    )
    db.add(account)
    db.commit()
    return {"ok": True, "accounts": _fb_accounts_list(db)}


@router.put("/facebook/accounts/{account_id}")
def update_facebook_account(account_id: int, body: FacebookAccountUpdate,
                            db: Session = Depends(get_db), _=Depends(require_admin)):
    account = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    if body.label.strip():
        account.label = body.label.strip()
    if body.cookies_json.strip():
        account.cookies_json = _validate_fb_cookies(body.cookies_json)
    if body.proxy_url is not None:
        account.proxy_url = _validate_fb_proxy(body.proxy_url) or None
    db.commit()
    return {"ok": True, "accounts": _fb_accounts_list(db)}


@router.post("/facebook/accounts/{account_id}/toggle")
def toggle_facebook_account(account_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    account = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    account.active = not account.active
    db.commit()
    return {"ok": True, "accounts": _fb_accounts_list(db)}


@router.delete("/facebook/accounts/{account_id}")
def delete_facebook_account(account_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    account = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    db.delete(account)
    db.commit()
    return {"ok": True, "accounts": _fb_accounts_list(db)}


@router.post("/facebook/test")
def test_facebook_connection(_=Depends(require_admin)):
    """
    Prueba real de conectividad: llama a search_posts() con un término genérico
    y retorna si las cookies funcionan o el error exacto.
    """
    from app.workers.scrapers.facebook import _load_cookies

    cookies = _load_cookies(settings.FB_COOKIES_FILE)
    if not cookies:
        return {"ok": False, "error": "Archivo de cookies no encontrado en el servidor", "message": "Archivo de cookies no encontrado en el servidor"}

    try:
        import facebook_scraper as fb
        count = 0
        gen = fb.get_posts_by_search(
            "noticias",
            page_limit=1,
            cookies=cookies,
        )
        for _ in gen:
            count += 1
            if count >= 5:
                break
        return {"ok": True, "posts_found": count, "message": f"Conexión exitosa — {count} posts encontrados"}
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "Error al conectar con Facebook — las cookies pueden haber expirado"}


@router.post("/facebook/trigger")
def trigger_facebook_scrape(_=Depends(require_admin)):
    """Dispara la tarea de scraping de Facebook inmediatamente (sin esperar el cron)."""
    from app.workers.tasks.scraping import scrape_facebook
    task = scrape_facebook.delay()
    return {"ok": True, "task_id": task.id, "message": "Tarea enviada a la cola"}
