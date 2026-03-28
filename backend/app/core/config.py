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
    # Tiempo de sesión en minutos. Configurable en .env → SESSION_TIMEOUT_MINUTES=60
    SESSION_TIMEOUT_MINUTES: int = 480

    # Notificaciones
    TELEGRAM_BOT_TOKEN: str = ""
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # APIs
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "SONAR Monitor 1.0"
    YOUTUBE_API_KEY: str = ""
    HUGGINGFACE_TOKEN: str = ""

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
    CHAT_ADVANCED_MODE: bool = False

    # Módulo 7 — Reconocimiento Visual
    FACE_RECOGNITION_ENABLED: bool = False  # activar en .env cuando haya fotos de referencia
    FACE_DISTANCE_THRESHOLD: float = 0.55   # distancia máxima para match (0=exacto, 1=muy diferente)
    FACES_DIR: str = "/app/storage/faces"   # ruta base de fotos de referencia

    # Entorno
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"


settings = Settings()
