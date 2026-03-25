"""
Notificaciones por Telegram Bot.
Completamente gratuito, sin límites prácticos.

Setup (una vez):
  1. Hablar con @BotFather en Telegram → /newbot → copiar token
  2. Cada usuario envía /start al bot → obtiene su chat_id
  3. El admin registra el chat_id en el perfil del usuario en SONAR
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

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
        f"{icon} *ALERTA SONAR* {icon}\n\n"
        f"*Entidad:* {alert_data['entity_name']}\n"
        f"*Tipo:* {rule}\n"
        f"*Severidad:* {severity}\n\n"
        f"{alert_data['message']}\n\n"
        f"🕐 {alert_data['triggered_at']}"
    )


def send_telegram(chat_id: str, alert_data: dict) -> bool:
    """
    Envía una alerta por Telegram.
    Retorna True si fue enviada correctamente.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.debug("TELEGRAM_BOT_TOKEN no configurado, omitiendo notificación.")
        return False

    url     = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       _format_message(alert_data),
        "parse_mode": "Markdown",
    }

    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
        if resp.status_code == 200:
            logger.info(f"Telegram enviado → chat_id {chat_id}")
            return True
        logger.warning(f"Telegram error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"Error enviando Telegram a {chat_id}: {e}")
        return False


def send_telegram_bulk(chat_ids: list[str], alert_data: dict) -> int:
    """Envía a múltiples destinatarios. Retorna cantidad de envíos exitosos."""
    return sum(1 for cid in chat_ids if send_telegram(cid, alert_data))
