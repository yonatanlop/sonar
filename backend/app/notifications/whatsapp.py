"""
Notificaciones por WhatsApp usando CallMeBot.
Completamente gratuito, sin límites documentados.

Setup por usuario (una vez):
  1. Agregar +34 644 62 08 61 a contactos de WhatsApp
  2. Enviarle el mensaje: "I allow callmebot to send me messages"
  3. Recibirás tu API key personal por WhatsApp
  4. El usuario registra su teléfono + api_key en su perfil SONAR

Formato del teléfono: código país + número, sin + ni espacios
  Ejemplo Colombia: 573001234567
  Ejemplo México:   5215512345678
"""
import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"

SEVERITY_ICON = {
    "low":      "ℹ️",
    "medium":   "⚠️",
    "high":     "🔴",
    "critical": "🚨",
}

RULE_TYPE_LABEL = {
    "volume_spike":       "Pico de Volumen",
    "negative_threshold": "Umbral de Negatividad",
    "bot_activity":       "Actividad de Bots",
    "keyword_critical":   "Keyword Crítica",
    "campaign_detected":  "Campaña Detectada",
    "hate_speech":        "Discurso de Odio",
}


def _format_message(alert_data: dict) -> str:
    icon     = SEVERITY_ICON.get(alert_data["severity"], "🔔")
    severity = alert_data["severity"].upper()
    rule     = RULE_TYPE_LABEL.get(alert_data["rule_type"], alert_data["rule_type"])

    return (
        f"{icon} ALERTA SONAR {icon}\n\n"
        f"Entidad: {alert_data['entity_name']}\n"
        f"Tipo: {rule}\n"
        f"Severidad: {severity}\n\n"
        f"{alert_data['message']}\n\n"
        f"Hora: {alert_data['triggered_at']}"
    )


def send_whatsapp(phone: str, api_key: str, alert_data: dict) -> bool:
    """
    Envía una alerta por WhatsApp usando CallMeBot.
    Retorna True si fue enviada correctamente.
    """
    if not phone or not api_key:
        logger.debug("WhatsApp: phone o api_key no configurados, omitiendo.")
        return False

    message = _format_message(alert_data)

    try:
        resp = httpx.get(
            CALLMEBOT_URL,
            params={
                "phone":  phone,
                "text":   message,
                "apikey": api_key,
            },
            timeout=15.0,
        )
        # CallMeBot retorna 200 con body "Message queued" si todo OK
        if resp.status_code == 200 and "queued" in resp.text.lower():
            logger.info(f"WhatsApp enviado → {phone[:6]}***")
            return True
        logger.warning(f"WhatsApp error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"Error enviando WhatsApp a {phone[:6]}***: {e}")
        return False


def send_whatsapp_bulk(recipients: list[dict], alert_data: dict) -> int:
    """
    Envía a múltiples destinatarios.
    recipients: [{"phone": "...", "api_key": "..."}, ...]
    Retorna cantidad de envíos exitosos.
    """
    count = 0
    for r in recipients:
        if send_whatsapp(r.get("phone", ""), r.get("api_key", ""), alert_data):
            count += 1
    return count


def send_admin_whatsapp(text: str) -> bool:
    """
    Envía un mensaje de texto libre al número de admin del sistema.
    Usado para alertas internas: cookies expiradas, fallos del scraper, etc.
    Requiere WHATSAPP_PHONE y CALLMEBOT_APIKEY en .env.
    """
    from app.core.config import settings

    if not settings.WHATSAPP_PHONE or not settings.CALLMEBOT_APIKEY:
        logger.debug("WHATSAPP_PHONE o CALLMEBOT_APIKEY no configurados, omitiendo.")
        return False

    try:
        resp = httpx.get(
            CALLMEBOT_URL,
            params={
                "phone":  settings.WHATSAPP_PHONE,
                "text":   text,
                "apikey": settings.CALLMEBOT_APIKEY,
            },
            timeout=15.0,
        )
        if resp.status_code == 200 and "queued" in resp.text.lower():
            logger.info(f"[WhatsApp Admin] Mensaje enviado → {settings.WHATSAPP_PHONE[:6]}***")
            return True
        logger.warning(f"[WhatsApp Admin] Error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"[WhatsApp Admin] Error: {e}")
        return False
