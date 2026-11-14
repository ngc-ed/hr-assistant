"""Pruebas unitarias de la cuenta de costo: agente, métricas y página web."""

from pathlib import Path

import pytest

from app.agent import Agent
from app.llm import Completion
from app.metrics import Metrics

INDEX = Path(__file__).resolve().parent.parent / "app" / "static" / "index.html"


class HalfCachedModel:
    """Modelo de guion: la primera llamada sale de la caché y la segunda no."""

    def __init__(self):
        self.replies = [
            Completion(
                text='{"tool": "get_employee", "args": {"employee_id": "EMP-0001"}}',
                input_tokens=10,
                output_tokens=2,
                cached=True,
            ),
            Completion(text='{"answer": "Hecho."}', input_tokens=30, output_tokens=4),
        ]

    def complete(self, _messages):
        """Devuelve la siguiente respuesta del guion.

        :param _messages: Conversación que recibe el modelo (no se usa)
        :type messages: list[dict]
        :return: La respuesta del guion
        :rtype: Completion
        """
        return self.replies.pop(0)


def test_cached_calls_are_counted_apart_and_are_not_billable(directory):
    result = Agent(HalfCachedModel(), directory, max_steps=3).run("¿EMP-0001?", [])
    assert result.answer == "Hecho."
    assert (result.input_tokens, result.output_tokens) == (40, 6)
    assert result.cached_calls == 1
    assert (result.billable_input_tokens, result.billable_output_tokens) == (30, 4)


def test_recorded_costs_add_up_in_the_metrics_snapshot():
    metrics = Metrics(slo_p95_ms=2000)
    metrics.record_cost(0.25)
    metrics.record_cost(0.5)
    assert metrics.snapshot(pid=1)["cost_usd"] == pytest.approx(0.75)


def test_page_shows_the_cost_and_the_model_unavailable_message():
    page = INDEX.read_text(encoding="utf-8")
    assert 'data-testid="cost"' in page
    assert 'data-testid="error"' in page
    assert "El modelo no está disponible. Intenta más tarde." in page
