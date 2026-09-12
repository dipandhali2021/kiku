"""Application settings, read from the environment.

Nothing secret has a default. If a required value is missing we want a loud
failure at startup, not a quiet fallback that leaks into production.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key) or default)
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_name: str = "Kiku API"
    version: str = "0.1.0"
    environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "development"))

    # Storage. SQLite locally, Postgres in production.
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "sqlite:///./kiku.db")
    )

    # Auth. Firebase project id is enough to verify ID tokens against Google's
    # public JWKS; no service-account key is needed for verification alone.
    firebase_project_id: str = field(
        default_factory=lambda: _env("FIREBASE_PROJECT_ID")
    )
    # Development escape hatch: accept a fake bearer token as a user id.
    # Refuses to switch on when ENVIRONMENT=production.
    auth_dev_mode: bool = field(default_factory=lambda: _env_bool("AUTH_DEV_MODE"))

    # LLM
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "gpt-4o-mini"))
    llm_base_url: str = field(
        default_factory=lambda: _env("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    llm_timeout_seconds: int = field(
        default_factory=lambda: _env_int("LLM_TIMEOUT_SECONDS", 45)
    )

    # Guardrails. Cost control belongs in the code from day one, not after the
    # first surprise bill.
    max_lines_per_lesson: int = field(
        default_factory=lambda: _env_int("MAX_LINES_PER_LESSON", 120)
    )
    max_subtitle_bytes: int = field(
        default_factory=lambda: _env_int("MAX_SUBTITLE_BYTES", 512_000)
    )
    daily_lesson_limit: int = field(
        default_factory=lambda: _env_int("DAILY_LESSON_LIMIT", 30)
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def dev_auth_allowed(self) -> bool:
        return self.auth_dev_mode and not self.is_production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
