"""Pruebas de la configuración de la sesión 4: entorno, claves y límite."""

import pytest

from app.config import Settings

SECRET = "secret-key-0123456789"


def test_misspelled_environment_is_rejected():
    with pytest.raises(ValueError, match="ENVIRONMENT"):
        Settings.from_env({"ENVIRONMENT": "prod"})


def test_zero_or_non_numeric_rate_limit_is_rejected():
    for raw in ("0", "abc"):
        with pytest.raises(ValueError, match="RATE_LIMIT_PER_MINUTE"):
            Settings.from_env({"RATE_LIMIT_PER_MINUTE": raw})


def test_api_keys_are_read_but_never_shown_in_repr():
    settings = Settings.from_env({"API_KEYS": f"web:{SECRET}"})

    assert settings.environment == "development"
    assert settings.rate_limit_per_minute == 30
    assert len(settings.api_keys) == 1
    assert SECRET not in repr(settings)
