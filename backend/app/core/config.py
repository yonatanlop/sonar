from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos
    DATABASE_URL: str
    POSTGRES_DB: str = "sonar_db"
    POSTGRES_USER: str = "sonar_user"
    POSTGRES_PASSWORD: str = "sonar_secret"

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"

    # Seguridad
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # Tiempo de sesión en minutos. Configurable en .env → SESSION_TIMEOUT_MINUTES=120
    SESSION_TIMEOUT_MINUTES: int = 120

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres")
        return v

    # Notificaciones
    TELEGRAM_BOT_TOKEN: str = ""
    ADMIN_TELEGRAM_CHAT_ID: str = ""   # chat_id del admin para alertas del sistema (ej: cookies expiradas)
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # APIs
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "SONAR Monitor 1.0"
    YOUTUBE_API_KEY: str = ""
    HUGGINGFACE_TOKEN: str = ""

    # Indexor — sistema externo de indexación de videos YouTube por subtítulos
    INDEXOR_API_URL: str = "https://live.arquitectura-test.xyz"
    INDEXOR_API_TOKEN: str = ""

    # Twitter / X (twscrape — sin API key oficial)
    # Ruta a la DB SQLite donde twscrape guarda las cuentas y sus cookies.
    # El volumen storage_data lo persiste entre reinicios del contenedor.
    TWITTER_ACCOUNTS_DB: str = "/app/storage/twscrape.db"
    # Ventana de búsqueda hacia atrás en días. Se añade since:YYYY-MM-DD a la query.
    # Default 7 días — cubre huecos si el sistema estuvo caído o la keyword es nueva.
    # Aumentar a 14-30 para monitoreo retrospectivo (más lento, más tweets por ciclo).
    TWITTER_LOOKBACK_DAYS: int = 7
    # Máximo de tweets por keyword por ciclo. Aumentar si lookback es largo.
    TWITTER_MAX_RESULTS: int = 100
    # Twitter API v2 Bearer Token (opcional, tier 2 cuando twscrape falla)
    # Obtener gratis en: developer.twitter.com → Projects & Apps → Keys and Tokens
    # Plan gratuito: 500K tweets/mes, búsqueda últimos 7 días.
    TWITTER_BEARER_TOKEN: str = ""
    # Proxy residencial para twscrape y Nitter (bypass Cloudflare en datacenters)
    # Formato: "http://usuario:contraseña@host:puerto"
    # Recomendado: webshare.io (10 proxies gratuitos permanentes)
    TWITTER_PROXY_URL: str = ""

    # NLP
    NLP_MODE: str = "api"   # 'api' | 'local'

    # Groq API (v2 — resúmenes y agentes con Llama 3 gratuito)
    # Obtener token gratis en: console.groq.com
    GROQ_API_KEY: str = ""
    SUMMARY_MODEL: str = "llama-3.1-8b-instant"  # modelo más rápido y gratuito de Groq

    # Bot Classifier ML (v2)
    BOT_THRESHOLD: float = 0.7  # probabilidad mínima para clasificar como "bot"

    # Módulo 13 — Chat Asistente RAG
    # false → Fase simple: cada pregunta es independiente (default)
    # true  → Fase avanzada: historial multi-turno incluido en el contexto
    CHAT_ADVANCED_MODE: bool = True

    # WhatsApp (Callmebot — gratuito)
    WHATSAPP_PHONE: str = ""      # número con código de país sin +  (ej: 573001234567)
    CALLMEBOT_APIKEY: str = ""    # apikey que envía Callmebot por WhatsApp

    # Instagram (pool de cuentas descartables — al menos 1 requerida para scraping)
    IG_ACCOUNT_1_USERNAME: str = ""
    IG_ACCOUNT_1_PASSWORD: str = ""
    IG_ACCOUNT_2_USERNAME: str = ""
    IG_ACCOUNT_2_PASSWORD: str = ""
    IG_LOOKBACK_DAYS: int = 3        # días hacia atrás para filtrar posts recientes

    # Facebook (cookies de sesión exportadas con Cookie-Editor desde facebook.com)
    FB_COOKIES_FILE: str = "/app/storage/fb_cookies.json"
    FB_LOOKBACK_DAYS: int = 3        # días hacia atrás para filtrar posts recientes

    # TikTok (TikTokApi v6 + Playwright — worker local con IP residencial)
    # Obtener ms_token: tiktok.com → DevTools → Application → Cookies → msToken
    TIKTOK_MS_TOKEN: str = ""
    TIKTOK_LOOKBACK_DAYS: int = 3
    TIKTOK_MAX_RESULTS: int = 30

    # Módulo 7 — Reconocimiento Visual
    FACE_RECOGNITION_ENABLED: bool = False  # activar en .env cuando haya fotos de referencia
    FACE_DISTANCE_THRESHOLD: float = 0.55   # distancia máxima para match (0=exacto, 1=muy diferente)
    FACES_DIR: str = "/app/storage/faces"   # ruta base de fotos de referencia

    # Módulo 8 — Búsqueda Inversa de Imágenes (todas opcionales)
    GOOGLE_CLOUD_API_KEY: str = ""   # Google Cloud Vision Web Detection (1 000 req/mes gratis)
    TINEYE_API_KEY: str = ""         # TinEye Reverse Image Search (100 búsquedas/mes gratis)
    BING_SEARCH_KEY: str = ""        # Bing Visual Search Azure (1 000 req/mes gratis)

    # Entorno
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"


settings = Settings()
