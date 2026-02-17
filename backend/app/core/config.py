from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """앱 전역 설정. .env 파일에서 환경 변수 로드."""

    # Database
    DATABASE_URL: str

    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # JWT
    JWT_SECRET_KEY: str | None = None
    JWT_ALGORITHM: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # OpenSearch
    OPENSEARCH_HOST: str = "opensearch"
    OPENSEARCH_PORT: int = 9200

    # Aladin API
    ALADIN_API_KEY: str | None = None

    # AI APIs
    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # App
    APP_ENV: str = "development"
    FRONTEND_URL: str | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
