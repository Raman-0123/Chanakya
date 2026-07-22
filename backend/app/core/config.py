"""Typed application configuration.

All settings load from environment / the repo-root `.env`. Nothing here raises
on a missing key — the platform is designed to degrade gracefully so it boots
with zero credentials and lights up capabilities as keys are added.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root .env  (backend/app/core/config.py -> repo root is 3 parents up)
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    environment: str = "development"
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8010
    frontend_origin: str = "http://localhost:3100"
    allowed_origins: str = ""
    process_role: str = "all"  # all | api | worker
    operator_pin: str = ""
    event_poll_seconds: int = 300
    event_stream_name: str = "chanakya:events"
    event_dead_letter_stream: str = "chanakya:events:dead"
    event_stream_maxlen: int = 5000

    # ---- LLM providers ----
    llm_primary_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    nvidia_api_key: str = ""
    nvidia_model: str = "meta/llama-3.3-70b-instruct"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # ---- Live data sources ----
    gdelt_enabled: bool = True
    open_meteo_enabled: bool = True
    eia_api_key: str = ""
    alpha_vantage_api_key: str = ""
    aisstream_api_key: str = ""
    newsapi_key: str = ""
    sanctions_enabled: bool = True
    opensanctions_api_key: str = ""  # OpenSanctions now requires a key for live search
    ppac_enabled: bool = True
    nasa_firms_map_key: str = ""

    # ---- Datastores ----
    database_url: str = (
        "postgresql+asyncpg://chanakya:chanakya_dev_pw@localhost:5432/chanakya"
    )
    redis_url: str = "redis://localhost:6379/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "chanakya_dev_pw"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # ---- Derived helpers ----
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def operator_pin_is_weak(self) -> bool:
        """True if the operator PIN is unset or a known placeholder/dev value.

        Mission activation is gated on this PIN, so a weak one is a real security
        gap in a hosted deployment — surfaced in /readyz and blocking readiness
        in production.
        """
        weak = {"", "change-this-for-hosting", "dev-local-pin", "changeme",
                "password", "0000", "1234"}
        return self.operator_pin.strip().lower() in weak or len(self.operator_pin.strip()) < 8

    @property
    def configured_llm_providers(self) -> list[str]:
        """Providers that have a key set, primary first."""
        available = {
            "groq": bool(self.groq_api_key),
            "gemini": bool(self.gemini_api_key),
            "nvidia": bool(self.nvidia_api_key),
            "openrouter": bool(self.openrouter_api_key),
            "deepseek": bool(self.deepseek_api_key),
        }
        ordered = [self.llm_primary_provider] + [
            p for p in available if p != self.llm_primary_provider
        ]
        return [p for p in ordered if available.get(p)]

    @property
    def cors_origins(self) -> list[str]:
        values = [self.frontend_origin]
        values.extend(v.strip() for v in self.allowed_origins.split(",") if v.strip())
        return list(dict.fromkeys(values))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
