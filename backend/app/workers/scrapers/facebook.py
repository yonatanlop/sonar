"""
Scraper de Facebook para SONAR.
Usa Playwright (Chromium headless) con cookies de sesión exportadas desde una cuenta real.
Requiere IP residencial — no funciona desde datacenters (Oracle, AWS, GCP).

Configuración:
  1. Instalar Cookie-Editor en Chrome
  2. Ir a facebook.com (logueado)
  3. Cookie-Editor → Export → guardar como fb_cookies.json en storage/
  4. Ejecutar el worker en una PC con IP residencial (ver docker-compose.facebook-worker.yml)
"""
import hashlib
import json
import logging
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import BaseScraper, keyword_matches_text, save_mention

logger = logging.getLogger(__name__)

DELAY_BETWEEN_SEARCHES = 45  # segundos entre búsquedas (más tiempo = menos detección)
POSTS_PER_SEARCH       = 12  # posts visibles sin scroll (~1 página)
PAGE_LOAD_WAIT_MS      = 6000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _load_cookies(cookies_file: str) -> Optional[dict]:
    path = Path(cookies_file)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            raw = json.load(f)
        if isinstance(raw, list):
            return {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
        if isinstance(raw, dict):
            return raw
    except Exception as e:
        logger.error(f"[Facebook] Error leyendo cookies desde {cookies_file}: {e}")
    return None


def _playwright_cookies(cookies_dict: dict) -> list:
    """Convierte dict {name: value} al formato que acepta Playwright."""
    return [
        {"name": k, "value": v, "domain": ".facebook.com", "path": "/"}
        for k, v in cookies_dict.items()
    ]


def _extract_post_id(url: str, text: str) -> str:
    """Extrae un ID estable del post a partir de la URL o el texto."""
    # Intentar extraer pfbid o story_fbid de la URL
    m = re.search(r'pfbid\w+', url)
    if m:
        return m.group(0)
    m = re.search(r'story_fbid[=%](\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r'/posts/(\d+)', url)
    if m:
        return m.group(1)
    # Fallback: hash del texto (estable entre runs)
    return hashlib.sha1(text[:200].encode()).hexdigest()[:16]


def _parse_reach_number(text: str) -> int:
    """Convierte '5,3 mil' o '2.2K' a entero."""
    text = text.lower().replace('\xa0', ' ')
    m = re.search(r'([\d.,]+)\s*(mil|k|m)?', text)
    if not m:
        return 0
    num_str = m.group(1).replace(',', '.').replace(' ', '')
    try:
        num = float(num_str)
    except ValueError:
        return 0
    mult = m.group(2) or ''
    if mult in ('mil', 'k'):
        num *= 1000
    elif mult == 'm':
        num *= 1_000_000
    return int(num)


def _diagnose_fb_page(page, term: str) -> None:
    """
    Cuando falta [role="feed"], inspecciona la página para distinguir entre:
    sesión expirada, checkpoint, bloqueo temporal, o búsqueda sin resultados.
    Guarda un screenshot en /app/storage/fb_debug_<ts>.png para revisión visual.
    """
    current_url = page.url

    # ── 1. Redirección a login ───────────────────────────────────
    if "login" in current_url or page.query_selector('input[name="email"]'):
        logger.error(
            f"[Facebook] SESIÓN EXPIRADA — redirigido a login. "
            f"URL: {current_url}. Actualiza fb_cookies.json."
        )
        return

    # ── 2. Checkpoint / captcha / 2FA ────────────────────────────
    if "checkpoint" in current_url or "two_step" in current_url:
        logger.error(
            f"[Facebook] CHECKPOINT DETECTADO — Facebook exige verificación adicional. "
            f"URL: {current_url}. Abre facebook.com en el navegador y completa la verificación."
        )
        return

    # ── 3. Bloqueo temporal ("temporarily blocked" / "bloqueado") ─
    body_text = ""
    try:
        body_text = (page.query_selector("body") or page).inner_text().lower()
    except Exception:
        pass

    block_keywords = ["temporarily blocked", "bloqueado temporalmente", "rate limit",
                      "you're blocked", "te hemos bloqueado", "unusual activity"]
    if any(kw in body_text for kw in block_keywords):
        logger.error(
            f"[Facebook] BLOQUEO TEMPORAL detectado para '{term}'. "
            "Facebook detectó actividad inusual. Esperar 30–60 min antes del próximo scrape."
        )
        return

    # ── 4. Sin resultados (feed existe pero vacío) ───────────────
    no_results_selectors = [
        '[aria-label="No results found"]',
        '[data-testid="no_results"]',
    ]
    for sel in no_results_selectors:
        if page.query_selector(sel):
            logger.info(f"[Facebook] '{term}' — sin resultados (búsqueda válida pero vacía)")
            return

    no_results_phrases = ["no hay resultados", "no results found", "sin resultados"]
    if any(p in body_text for p in no_results_phrases):
        logger.info(f"[Facebook] '{term}' — sin resultados (búsqueda válida pero vacía)")
        return

    # ── 5. Página vacía / "Not Found" — detección de bot ────────
    if not body_text.strip() or body_text.strip() in ("not found", "error"):
        logger.error(
            f"[Facebook] BOT DETECTADO para '{term}' — Facebook sirvió página vacía. "
            "Aumentar DELAY_BETWEEN_SEARCHES o renovar cookies con una sesión más activa."
        )
        try:
            ts = int(time.time())
            page.screenshot(path=f"/app/storage/fb_debug_{ts}.png", full_page=False)
            logger.warning(f"[Facebook] Screenshot guardado en /app/storage/fb_debug_{ts}.png")
        except Exception:
            pass
        return

    # ── 6. Caso desconocido — registrar título + screenshot ──────
    try:
        title = page.title()
    except Exception:
        title = "(no disponible)"

    logger.warning(
        f"[Facebook] Feed no encontrado para '{term}'. "
        f"Título: '{title}' | URL: {current_url}"
    )

    try:
        ts = int(time.time())
        screenshot_path = f"/app/storage/fb_debug_{ts}.png"
        page.screenshot(path=screenshot_path, full_page=False)
        logger.warning(f"[Facebook] Screenshot guardado en {screenshot_path} para diagnóstico")
    except Exception as ss_err:
        logger.debug(f"[Facebook] No se pudo guardar screenshot: {ss_err}")


class FacebookScraper(BaseScraper):
    """
    Scraper de Facebook usando Playwright con cookies de sesión.
    Requiere ejecutarse en un host con IP residencial.
    """
    platform_code = "facebook"

    def __init__(self, db: Session):
        super().__init__(db)
        from app.core.config import settings
        self._cookies = _load_cookies(settings.FB_COOKIES_FILE)
        if not self._cookies:
            raise RuntimeError(
                f"Facebook: archivo de cookies no encontrado en '{settings.FB_COOKIES_FILE}'. "
                "Exporta las cookies desde facebook.com con Cookie-Editor."
            )

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("playwright no instalado. Ejecuta: pip install playwright && playwright install chromium")

        from app.core.config import settings
        saved_total = 0
        since = datetime.now(timezone.utc) - timedelta(days=settings.FB_LOOKBACK_DAYS)
        seen_terms: set[str] = set()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",  # oculta navigator.webdriver
                    "--disable-dev-shm-usage",
                ],
            )
            ctx = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1366, "height": 768},
                locale="es-CO",
                timezone_id="America/Bogota",
            )
            ctx.add_cookies(_playwright_cookies(self._cookies))
            ctx.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                window.chrome = { runtime: {} };
            """)

            # Warm-up: visitar facebook.com home antes de buscar
            warmup = ctx.new_page()
            try:
                warmup.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                if "login" in warmup.url:
                    logger.error("[Facebook] Cookies inválidas — redirigido a login en warm-up. Actualiza fb_cookies.json.")
                    browser.close()
                    return saved_total
                # Simular actividad humana antes de buscar
                warmup.mouse.wheel(0, 300)
                time.sleep(2)
                warmup.mouse.wheel(0, -150)
                time.sleep(1)
                logger.info(f"[Facebook] Sesión activa — URL warm-up: {warmup.url}")
            except Exception as e:
                logger.warning(f"[Facebook] Warm-up falló (continuando de todas formas): {e}")
            finally:
                warmup.close()

            for keyword_obj in keywords:
                term = keyword_obj.keyword.strip()
                if not term or term in seen_terms:
                    continue
                seen_terms.add(term)
                try:
                    saved = self._search_keyword(ctx, term, entity, keyword_obj, since)
                    saved_total += saved
                except Exception as e:
                    logger.warning(f"[Facebook] Error buscando '{term}': {e}")
                time.sleep(DELAY_BETWEEN_SEARCHES)

            browser.close()

        return saved_total

    def _search_keyword(self, ctx, term: str, entity: Entity, keyword_obj: Keyword, since: datetime) -> int:
        page = ctx.new_page()
        saved = 0
        raw_count = 0

        try:
            url = f"https://www.facebook.com/search/posts/?q={urllib.parse.quote(term)}"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            try:
                page.wait_for_selector('[role="feed"]', timeout=12000)
            except Exception:
                _diagnose_fb_page(page, term)
                logger.info(f"[Facebook] Reintentando '{term}' en 30 segundos...")
                time.sleep(30)
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector('[role="feed"]', timeout=12000)
                except Exception:
                    logger.warning(f"[Facebook] Reintento fallido para '{term}', omitiendo.")
                    return 0

            page.wait_for_timeout(PAGE_LOAD_WAIT_MS)

            post_cards = page.query_selector_all('[role="feed"] > div')
            raw_count = len(post_cards)

            for card in post_cards:
                # ── Texto del post ──────────────────────────────────
                text = ""
                for el in card.query_selector_all('[dir="auto"]'):
                    t = el.inner_text().strip()
                    if len(t) > 15:
                        text = t
                        break

                if not text:
                    continue

                if not keyword_matches_text(text, keyword_obj):
                    continue

                # ── URL del post ────────────────────────────────────
                post_url = ""
                for a in card.query_selector_all("a[href]"):
                    href = a.get_attribute("href") or ""
                    if any(x in href for x in ["/posts/", "story_fbid", "pfbid", "/videos/"]):
                        post_url = href
                        break
                if not post_url:
                    for a in card.query_selector_all("a[href]"):
                        href = a.get_attribute("href") or ""
                        if href.startswith("https://www.facebook.com/"):
                            post_url = href
                            break

                post_id = _extract_post_id(post_url, text)

                # ── Autor ───────────────────────────────────────────
                author_el = card.query_selector("h2 a, h3 a, strong a")
                username = author_el.inner_text().strip() if author_el else ""

                # ── Reach ───────────────────────────────────────────
                reactions = 0
                shares = 0
                for span in card.query_selector_all("span"):
                    t = span.inner_text()
                    if "compartido" in t.lower() or "shares" in t.lower():
                        shares = _parse_reach_number(t)
                    if "reacciones" in t.lower() or "reactions" in t.lower():
                        reactions = _parse_reach_number(t)
                reach = reactions + shares

                # Guardar mención dentro de un savepoint para que un error
                # en un post no corrompa la sesión completa
                try:
                    sp = self.db.begin_nested()
                    mention = save_mention(
                        db=self.db,
                        platform_id=self.platform.id,
                        entity_id=entity.id,
                        external_id=f"fb_{post_id}",
                        content=text[:2000],
                        author_username=username or None,
                        author_ext_id=None,
                        url=post_url or None,
                        published_at=None,
                        country_code=entity.country_code,
                        reach=reach,
                        matched_keywords=[keyword_obj],
                    )
                    sp.commit()
                    if mention:
                        saved += 1
                except Exception as card_err:
                    sp.rollback()
                    logger.debug(f"[Facebook] Error guardando post '{post_id}': {card_err}")

        except Exception as e:
            logger.error(f"[Facebook] Error en _search_keyword('{term}'): {e}", exc_info=True)
        finally:
            page.close()

        logger.info(f"[Facebook] '{term}' → {raw_count} posts recibidos, {saved} guardados")
        return saved
