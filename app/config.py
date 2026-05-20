from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Brayden IBI API"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(..., description="Async PostgreSQL DSN (asyncpg)")
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30

    # ── Supabase / Auth ───────────────────────────────────────────────────────
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anon key")
    supabase_service_role_key: str = Field(..., description="Supabase service role key")
    supabase_jwt_secret: str = Field(..., description="JWT secret from Supabase project settings")
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "authenticated"

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_allow_credentials: bool = True

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ── Storage ──────────────────────────────────────────────────────────────
    supabase_storage_bucket_compliance: str = "compliance-docs"
    supabase_storage_bucket_payroll: str = "payroll-exports"
    supabase_storage_bucket_assets: str = "trust-assets"
    supabase_storage_signed_url_ttl: int = 900  # 15 min

    # ── Security ─────────────────────────────────────────────────────────────
    rate_limit_requests_per_minute: int = 60
    request_id_header: str = "X-Request-ID"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v  # type: ignore[return-value]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
