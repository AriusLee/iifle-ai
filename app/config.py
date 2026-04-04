from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://iifle:iifle_dev_password@localhost:5432/iifle"
    REDIS_URL: str = "redis://localhost:6379/0"

    @model_validator(mode="after")
    def fix_database_url(self):
        """Render provides postgresql:// but asyncpg needs postgresql+asyncpg://"""
        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self

    S3_BUCKET: str = "iifle-documents"
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "iifle_minio"
    S3_SECRET_KEY: str = "iifle_minio_secret"
    S3_REGION: str = "us-east-1"

    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    GROQ_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    AI_PROVIDER: str = "groq"  # "groq" (free, Qwen3) or "deepseek" (production)

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    CORS_ORIGINS: list[str] = ["http://localhost:2020", "http://localhost:2050"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
