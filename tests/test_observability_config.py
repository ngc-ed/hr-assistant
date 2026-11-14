"""Pruebas unitarias de la configuración de observabilidad."""

import pytest

from app.config import ConfigError, load_settings


def test_observability_settings_use_safe_defaults():
    settings = load_settings({})
    assert settings.service_name == "hr-assistant"
    assert settings.slo_p95_ms == 2000
    assert settings.tracing_enabled is False
    assert settings.hide_inputs is True
    assert settings.hide_outputs is True


@pytest.mark.parametrize(
    ("variable", "value"),
    [("SLO_P95_MS", "0"), ("LANGSMITH_TRACING", "quizas")],
)
def test_invalid_observability_value_stops_startup(variable, value):
    with pytest.raises(ConfigError) as error:
        load_settings({variable: value})
    assert variable in str(error.value)


def test_tracing_needs_the_flag_and_the_key_and_never_keeps_the_key():
    without_key = load_settings({"LANGSMITH_TRACING": "true"})
    assert without_key.tracing_enabled is False
    secret = "lsv2-secret-key"
    with_key = load_settings(
        {"LANGSMITH_TRACING": "TRUE", "LANGSMITH_API_KEY": secret}
    )
    assert with_key.tracing_enabled is True
    assert secret not in repr(with_key)
