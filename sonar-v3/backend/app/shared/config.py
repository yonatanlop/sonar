from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://sonar:sonar@db-v3:5432/sonar_v3"
    REDIS_URL: str = "redis://redis-v3:6379/0"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALGORITHM: str = "HS256"

    FRONTEND_URL: str = "http://localhost:3001"

    NLP_MODE: str = "api"
    GROQ_API_KEY: str = ""

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    YOUTUBE_API_KEY: str = ""

    IG_ACCOUNT_1_USERNAME: str = ""
    IG_ACCOUNT_1_PASSWORD: str = ""
    FB_COOKIES_FILE: str = ""

    FACE_RECOGNITION_ENABLED: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
