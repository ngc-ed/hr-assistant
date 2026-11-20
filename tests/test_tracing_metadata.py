"""Pruebas unitarias de los metadatos de las trazas de LangSmith (punto 7).

``langsmith`` se reemplaza por un registro: no hay red ni clave real.
"""

from contextlib import contextmanager

import langsmith

QUESTION = "¿Quién es EMP-0004?"
REQUIRED = {"request_id", "client", "route", "model", "cost_usd"}
API_KEY = "clave-de-prueba-0123456789"


def test_traces_carry_the_metadata_and_hide_the_text(make_client, monkeypatch):
    seen = {"clients": [], "contexts": []}

    class RecordingClient:
        """Cliente falso que anota con qué argumentos se creó."""

        def __init__(self, *_args, **kwargs):
            seen["clients"].append(kwargs)

    @contextmanager
    def recording_context(**kwargs):
        seen["contexts"].append(kwargs)
        yield

    monkeypatch.setattr(langsmith, "Client", RecordingClient)
    monkeypatch.setattr(langsmith, "tracing_context", recording_context)
    env = {
        "LANGSMITH_TRACING": "true",
        "LANGSMITH_API_KEY": "test-key",
        "HIDE_INPUTS": "true",
        "HIDE_OUTPUTS": "true",
        "API_KEYS": f"tester:{API_KEY}",
    }
    client = make_client(env=env)
    response = client.post(
        "/ask", json={"question": QUESTION}, headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 200
    assert seen["clients"][0]["hide_inputs"] is True
    assert seen["clients"][0]["hide_outputs"] is True
    metadata = seen["contexts"][-1]["metadata"]
    assert REQUIRED <= set(metadata)
    assert metadata["request_id"] == response.json()["request_id"]
    assert metadata["client"] == "tester"
    assert metadata["cost_usd"] == response.json()["cost_usd"]
    assert QUESTION not in repr(seen) and API_KEY not in repr(seen)
