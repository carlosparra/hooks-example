"""Pruebas de ``app.config`` para las variables de costos (sesion 3)."""

from pathlib import Path

import pytest

from app.config import Settings

GATEWAY_ENV = {
    "MODEL_PROVIDER": "gateway",
    "CF_ACCOUNT_ID": "account-1",
    "CF_GATEWAY_ID": "gateway-1",
    "CF_API_TOKEN": "token-super-secreto",
}


def test_fake_provider_needs_no_cloudflare_values_and_uses_cost_defaults():
    settings = Settings.from_env({})

    assert settings.cf_account_id == ""
    assert settings.cf_gateway_id == "default"
    assert settings.cf_api_token == ""
    assert settings.model_small == "@cf/meta/llama-3.1-8b-instruct-fast"
    assert settings.model_large == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert settings.routing is True
    assert settings.router_max_chars == 80
    assert settings.history_window == 6
    assert settings.model_max_tokens == 300
    assert settings.model_temperature == 0
    assert settings.cache_ttl_seconds == 0
    assert Path(settings.prices_path).parts[-2:] == ("data", "model_prices.json")


@pytest.mark.parametrize("missing", ["CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN"])
def test_gateway_does_not_start_without_a_cloudflare_variable(missing):
    environ = {**GATEWAY_ENV, missing: ""}

    with pytest.raises(ValueError, match=missing):
        Settings.from_env(environ)


def test_aig_token_is_optional_read_from_env_and_hidden_from_the_repr():
    without_token = Settings.from_env(GATEWAY_ENV)
    with_token = Settings.from_env({**GATEWAY_ENV, "CF_AIG_TOKEN": " aig-secreto "})

    assert without_token.cf_aig_token == ""
    assert with_token.cf_aig_token == "aig-secreto"
    assert "aig-secreto" not in repr(with_token)


def test_gateway_token_is_hidden_from_the_settings_repr():
    settings = Settings.from_env(GATEWAY_ENV)

    assert settings.cf_api_token == "token-super-secreto"
    assert "token-super-secreto" not in repr(settings)
