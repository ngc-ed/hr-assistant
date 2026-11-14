"""Pruebas unitarias de las trazas opcionales en LangSmith, sin red."""

import langsmith

from app.config import load_settings
from app.tracing import Tracing


def test_disabled_tracing_never_creates_a_client(monkeypatch):
    def forbidden_client(*args, **kwargs):
        raise AssertionError("no se debe crear un cliente de LangSmith")

    monkeypatch.setattr(langsmith, "Client", forbidden_client)
    tracing = Tracing(load_settings({}))
    assert tracing.enabled is False
    with tracing.context("req-1"):
        pass


def test_enabled_tracing_creates_one_client_that_hides_what_is_configured(
    monkeypatch,
):
    created = []

    class RecordingClient:
        """Cliente falso que solo anota con qué argumentos se creó."""

        def __init__(self, *_args, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(langsmith, "Client", RecordingClient)
    settings = load_settings(
        {
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_API_KEY": "test-key",
            "HIDE_INPUTS": "false",
        }
    )
    tracing = Tracing(settings)
    assert tracing.enabled is True
    with tracing.context("req-1"):
        pass
    with tracing.context("req-2"):
        pass
    assert len(created) == 1
    assert created[0]["hide_inputs"] is False
    assert created[0]["hide_outputs"] is True
