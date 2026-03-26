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

    # NLP
    NLP_MODE: str = "api"   # 'api' | 'local'

    # Groq API (v2 — resúmenes y agentes con Llama 3 gratuito)
    # Obtener token gratis en: console.groq.com
    GROQ_API_KEY: str = ""
    SUMMARY_MODEL: str = "llama-3.1-8b-instant"  # modelo más rápido y gratuito de Groq

    # Bot Classifier ML (v2)
    BOT_THRESHOLD: float = 0.7  # probabilidad mínima para clasificar como "bot"

    # Módulo 7 — Reconocimiento Visual
    FACE_RECOGNITION_ENABLED: bool = False  # activar en .env cuando haya fotos de referencia
    FACE_DISTANCE_THRESHOLD: float = 0.55   # distancia máxima para match (0=exacto, 1=muy diferente)
    FACES_DIR: str = "/app/storage/faces"   # ruta base de fotos de referencia

    # Entorno
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"


settings = Settings()
