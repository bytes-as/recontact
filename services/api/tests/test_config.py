"""G004: typed config, NCBI_EMAIL warning, required admin token."""

import logging

import pytest

from app.config import ENV_KEYS, ConfigError, load_settings


def _required(**extra: str) -> dict[str, str]:
    base = {"ADMIN_TOKEN": "admin-secret"}
    base.update(extra)
    return base


def test_defaults_and_types() -> None:
    settings = load_settings(
        _required(
            FALKORDB_PORT="6380",
            KB_BATCH_SIZE="100",
            NCBI_CACHE_HOURS="6",
            LLM_DAILY_BUDGET_CALLS="12",
            HANDOFF_SWEEP_SECONDS="15",
            SANDBOX_TTL_MINUTES="30",
            SANDBOX_MAX="10",
            KB_AUTOLOAD="false",
            LIVE_LOOKUPS="true",
            NCBI_EMAIL="lab@example.com",
            CORS_ORIGINS="http://localhost:3001, https://app.example",
            KB_SCOPE="dev",
        )
    )
    assert settings.falkordb_host == "localhost"
    assert settings.falkordb_port == 6380
    assert settings.kb_scope == "dev"
    assert settings.kb_autoload is False
    assert settings.kb_batch_size == 100
    assert settings.live_lookups is True
    assert settings.ncbi_cache_hours == 6
    assert settings.llm_daily_budget_calls == 12
    assert settings.handoff_sweep_seconds == 15
    assert settings.sandbox_ttl_minutes == 30
    assert settings.sandbox_max == 10
    assert settings.ncbi_tool == "recontact"
    assert settings.cors_origins == ["http://localhost:3001", "https://app.example"]
    assert settings.watch_cron == "0 6 * * *"
    assert settings.web_base_url == "http://localhost:3001"
    assert settings.next_public_api_url == "http://localhost:8000"
    assert settings.admin_token == "admin-secret"


def test_every_env_example_key_is_a_setting() -> None:
    field_names = {name.upper() for name in load_settings(_required()).__class__.model_fields}
    assert field_names == set(ENV_KEYS)


def test_missing_ncbi_email_disables_live_lookups(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="recontact.config"):
        settings = load_settings(_required(LIVE_LOOKUPS="true"))
    assert settings.ncbi_email == ""
    assert settings.live_lookups is False
    assert "NCBI_EMAIL" in caplog.text


def test_present_ncbi_email_keeps_live_lookups(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="recontact.config"):
        settings = load_settings(_required(NCBI_EMAIL="lab@example.com"))
    assert settings.live_lookups is True
    assert "NCBI_EMAIL" not in caplog.text


@pytest.mark.parametrize("env", [{}, {"ADMIN_TOKEN": ""}, {"ADMIN_TOKEN": "   "}])
def test_missing_admin_token_fails(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        load_settings(env)


def test_bad_scope_fails() -> None:
    with pytest.raises(ConfigError):
        load_settings(_required(KB_SCOPE="all"))
