"""Pruebas unitarias de la configuración nueva de la sesión 3 (costos)."""

from pathlib import Path

import pytest

from app.config import ConfigError, load_settings


def test_cost_settings_use_the_documented_defaults():
    settings = load_settings({})
    assert settings.cf_gateway_id == "default"
    assert settings.model_small == "@cf/meta/llama-3.1-8b-instruct-fast"
    assert settings.model_large == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert settings.routing is True
    assert settings.router_max_chars == 80
    assert settings.history_window == 6
    assert settings.model_max_tokens == 300
    assert settings.model_temperature == 0
    assert settings.cache_ttl_seconds == 0
    assert Path(settings.prices_path) == Path("data/model_prices.json")


def test_gateway_settings_never_show_the_token(gateway_env, token):
    settings = load_settings(gateway_env)
    assert settings.model_provider == "gateway"
    assert settings.cf_api_token == token
    assert token not in repr(settings)


@pytest.mark.parametrize(
    "variable", ["CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN"]
)
def test_gateway_without_a_cloudflare_variable_does_not_start(
    variable, gateway_env, token
):
    with pytest.raises(ConfigError) as error:
        load_settings({**gateway_env, variable: ""})
    assert variable in str(error.value)
    assert token not in str(error.value)


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("HISTORY_WINDOW", "-1"),
        ("MODEL_TEMPERATURE", "x"),
        ("CACHE_TTL_SECONDS", "-5"),
        ("ROUTER_MAX_CHARS", "0"),
        ("ROUTING", "quizas"),
    ],
)
def test_invalid_lever_value_stops_startup(variable, value):
    with pytest.raises(ConfigError) as error:
        load_settings({variable: value})
    assert variable in str(error.value)
