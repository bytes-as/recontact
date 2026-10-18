"""Typed settings for every variable in `.env.example`."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger("recontact.config")

ENV_KEYS: tuple[str, ...] = (
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_PASSWORD",
    "KB_SCOPE",
    "KB_AUTOLOAD",
    "KB_BATCH_SIZE",
    "NCBI_EMAIL",
    "NCBI_API_KEY",
    "NCBI_TOOL",
    "LIVE_LOOKUPS",
    "NCBI_CACHE_HOURS",
    "OPENROUTER_API_KEY",
    "LLM_MODEL",
    "LLM_DAILY_BUDGET_CALLS",
    "ADMIN_TOKEN",
    "CORS_ORIGINS",
    "WATCH_CRON",
    "HANDOFF_SWEEP_SECONDS",
    "SANDBOX_TTL_MINUTES",
    "SANDBOX_MAX",
    "WEB_BASE_URL",
    "NEXT_PUBLIC_API_URL",
)

_LIST_KEYS = frozenset({"CORS_ORIGINS"})
_BOOL_KEYS = frozenset({"KB_AUTOLOAD", "LIVE_LOOKUPS"})
_INT_KEYS = frozenset(
    {
        "FALKORDB_PORT",
        "KB_BATCH_SIZE",
        "NCBI_CACHE_HOURS",
        "LLM_DAILY_BUDGET_CALLS",
        "HANDOFF_SWEEP_SECONDS",
        "SANDBOX_TTL_MINUTES",
        "SANDBOX_MAX",
    }
)
_SCOPES = frozenset({"sf", "core", "dev"})

_settings: Settings | None = None


class ConfigError(RuntimeError):
    """Raised when a required setting is missing. Startup must stop."""


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    kb_scope: str = "sf"
    kb_autoload: bool = True
    kb_batch_size: int = 2000
    ncbi_email: str = ""
    ncbi_api_key: str = ""
    ncbi_tool: str = "recontact"
    live_lookups: bool = True
    ncbi_cache_hours: int = 24
    openrouter_api_key: str = ""
    llm_model: str = ""
    llm_daily_budget_calls: int = 300
    admin_token: str
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3001"])
    watch_cron: str = "0 6 * * *"
    handoff_sweep_seconds: int = 30
    sandbox_ttl_minutes: int = 120
    sandbox_max: int = 50
    web_base_url: str = "http://localhost:3001"
    next_public_api_url: str = "http://localhost:8000"


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce(key: str, text: str) -> object:
    if key in _LIST_KEYS:
        return _split_list(text)
    if key in _BOOL_KEYS:
        return _as_bool(text)
    if key in _INT_KEYS:
        return int(text)
    return text


def load_settings(source: Mapping[str, str] | None = None) -> Settings:
    """Read settings. A blank NCBI email disables live lookups. A blank admin token fails."""
    env = os.environ if source is None else source
    if not str(env.get("ADMIN_TOKEN", "")).strip():
        raise ConfigError("missing required setting: ADMIN_TOKEN")

    raw: dict[str, object] = {}
    for key in ENV_KEYS:
        if key == "ADMIN_TOKEN":
            raw["admin_token"] = str(env.get(key, "")).strip()
            continue
        value = env.get(key)
        if value is None or str(value).strip() == "":
            continue
        raw[key.lower()] = _coerce(key, str(value).strip())

    settings = Settings.model_validate(raw)
    if settings.kb_scope not in _SCOPES:
        raise ConfigError("KB_SCOPE must be sf, core, or dev")
    if not settings.ncbi_email:
        log.warning("NCBI_EMAIL is not set; live lookups are disabled")
        settings = settings.model_copy(update={"live_lookups": False})
    return settings


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings(os.environ)
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
