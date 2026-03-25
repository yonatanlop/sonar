"""
Notificaciones por Email usando Gmail SMTP.
Gratuito con cuenta Gmail (hasta 500 emails/día).

Setup:
  1. Tener cuenta Gmail
  2. Activar verificación en 2 pasos en la cuenta
  3. Ir a Seguridad → Contraseñas de aplicación → Generar una
  4. Copiar la contraseña de 16 caracteres al .env como GMAIL_APP_PASSWORD

Nota: usar GMAIL_APP_PASSWORD, NO la contraseña personal de Gmail.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

SEVERITY_COLOR = {
    "critical": "#dc2626",
    "high":     "#ea580c",
    "medium":   "#d97706",
    "low":      "#2563eb",
}

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


def _build_html(alert_data: dict) -> str:
    color    = SEVERITY_COLOR.get(alert_data["severity"], "#6b7280")
    severity = alert_data["severity"].upper()
    icon     = SEVERITY_ICON.get(alert_data["severity"], "🔔")
    rule     = RULE_TYPE_LABEL.get(alert_data["rule_type"], alert_data["rule_type"])

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background: #f9fafb; padding: 24px; margin: 0;">
      <div style="max-width: 560px; margin: 0 auto; background: white;
                  border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <div style="background: {color}; padding: 20px 24px;">
          <h1 style="color: white; margin: 0; font-size: 18px;">
            {icon} Alerta SONAR — {severity}
          </h1>
        </div>

        <!-- Contenido -->
        <div style="padding: 24px;">
          <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
            <tr>
              <td style="padding: 8px 0; color: #6b7280; font-size: 13px; width: 120px;">Entidad</td>
              <td style="padding: 8px 0; font-weight: 600; font-size: 13px;">
                {alert_data['entity_name']}
              </td>
            </tr>
            <tr style="border-top: 1px solid #f3f4f6;">
              <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Tipo de alerta</td>
              <td style="padding: 8px 0; font-size: 13px;">{rule}</td>
            </tr>
            <tr style="border-top: 1px solid #f3f4f6;">
              <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Severidad</td>
              <td style="padding: 8px 0;">
                <span style="background: {color}20; color: {color};
                             padding: 2px 10px; border-radius: 99px;
                             font-size: 12px; font-weight: 700;">
                  {severity}
                </span>
              </td>
            </tr>
            <tr style="border-top: 1px solid #f3f4f6;">
              <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Fecha y hora</td>
              <td style="padding: 8px 0; font-size: 13px;">{alert_data['triggered_at']}</td>
            </tr>
          </table>

          <!-- Descripción -->
          <div style="background: #f9fafb; border-left: 3px solid {color};
                      padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 13px; color: #374151; line-height: 1.6;">
              {alert_data['message']}
            </p>
          </div>

          <a href="{settings.FRONTEND_URL}/alerts"
             style="display: inline-block; background: {color}; color: white;
                    text-decoration: none; padding: 10px 20px; border-radius: 8px;
                    font-size: 13px; font-weight: 600;">
            Ver en Dashboard →
          </a>
        </div>

        <!-- Footer -->
        <div style="padding: 16px 24px; background: #f9fafb;
                    border-top: 1px solid #e5e7eb; text-align: center;">
          <p style="margin: 0; font-size: 11px; color: #9ca3af;">
            SONAR — Sistema de Monitoreo Reputacional · Este mensaje es confidencial
          </p>
        </div>
      </div>
    </body>
    </html>
    """


def send_email(to_email: str, alert_data: dict) -> bool:
    """
    Envía una alerta por email usando Gmail SMTP.
    Retorna True si fue enviada correctamente.
    """
    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASSWORD:
        logger.debug("Gmail no configurado, omitiendo notificación por email.")
        return False

    severity = alert_data["severity"].upper()
    icon     = SEVERITY_ICON.get(alert_data["severity"], "🔔")
    subject  = f"[SONAR] {icon} Alerta {severity} — {alert_data['entity_name']}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"SONAR Alertas <{settings.GMAIL_USER}>"
    msg["To"]      = to_email

    msg.attach(MIMEText(_build_html(alert_data), "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_USER, to_email, msg.as_string())
        logger.info(f"Email enviado → {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail SMTP: error de autenticación. Verificar GMAIL_APP_PASSWORD.")
        return False
    except Exception as e:
        logger.error(f"Error enviando email a {to_email}: {e}")
        return False


def send_email_bulk(emails: list[str], alert_data: dict) -> int:
    """Envía a múltiples destinatarios. Retorna cantidad de envíos exitosos."""
    return sum(1 for email in emails if send_email(email, alert_data))
