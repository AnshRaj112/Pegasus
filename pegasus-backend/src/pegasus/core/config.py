from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pegasus import __version__ as package_version


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PEGASUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Pegasus"
    version: str = package_version
    environment: str = Field(default="development", description="e.g. development, staging, production")
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = Field(
        default="postgresql+asyncpg://pegasus:pegasus@localhost:5432/pegasus",
        description="SQLAlchemy async URL (e.g. postgresql+asyncpg://...)",
    )

    cors_origins: str = Field(
        default="",
        description="Comma-separated allowed origins; empty disables CORS middleware",
    )

    validation_max_upload_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
        description="Max total bytes per uploaded CSV for POST /validate",
    )
    validation_mismatch_sample_limit: int = Field(
        default=100,
        ge=0,
        le=10_000,
        description="Max mismatch rows returned in mismatch_samples",
    )
    enable_validation_persistence: bool = Field(
        default=False,
        description="Persist validation runs and mismatch rows to PostgreSQL",
    )

    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
