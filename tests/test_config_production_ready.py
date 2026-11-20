"""Pruebas unitarias de la configuración nueva del reto de producción."""

import pytest

from app.config import ConfigError, load_settings


def test_new_settings_have_the_documented_defaults():
    settings = load_settings({})
    assert settings.max_answer_chars == 2000
    assert settings.model_max_retries == 2


def test_new_settings_read_the_environment_and_reject_invalid_values():
    settings = load_settings({"MAX_ANSWER_CHARS": "500", "MODEL_MAX_RETRIES": "0"})
    assert (settings.max_answer_chars, settings.model_max_retries) == (500, 0)
    for name, value in (
        ("MAX_ANSWER_CHARS", "0"),
        ("MAX_ANSWER_CHARS", "mucho"),
        ("MODEL_MAX_RETRIES", "-1"),
        ("MODEL_MAX_RETRIES", "dos"),
    ):
        with pytest.raises(ConfigError, match=name):
            load_settings({name: value})
