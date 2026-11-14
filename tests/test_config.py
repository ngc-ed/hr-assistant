"""Pruebas unitarias de la configuración."""

from pathlib import Path

import pytest

from app.config import ConfigError, load_settings


def test_missing_variables_use_the_documented_defaults():
    settings = load_settings({})
    assert settings.model_provider == "fake"
    assert settings.agent_max_steps == 3
    assert settings.max_question_chars == 2000
    assert Path(settings.employees_path) == Path("data/employees.json")


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("AGENT_MAX_STEPS", "0"),
        ("MAX_QUESTION_CHARS", "abc"),
        ("MODEL_PROVIDER", "openai"),
    ],
)
def test_invalid_value_stops_startup_with_a_clear_message(variable, value):
    with pytest.raises(ConfigError) as error:
        load_settings({variable: value})
    assert issubclass(ConfigError, ValueError)
    assert variable in str(error.value)
