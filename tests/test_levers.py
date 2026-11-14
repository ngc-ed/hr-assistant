"""Pruebas unitarias de las palancas de costo: enrutamiento y ventana de historial."""

import pytest

from app.config import load_settings
from app.levers import choose_model, window_history

SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("COMPARA Ventas y Finanzas", "keyword:compara"),
        ("¿Por Qué renunció EMP-0004?", "keyword:por qué"),
        ("Resume el área de Ventas", "keyword:resume"),
        ("Dame a todos los de Finanzas", "keyword:todos"),
    ],
)
def test_complex_keywords_route_to_the_large_model_regardless_of_case(
    question, reason
):
    route = choose_model(question, load_settings({}))
    assert (route.model, route.reason) == (LARGE, reason)


def test_question_of_exactly_the_router_limit_goes_to_the_small_model():
    settings = load_settings({"ROUTER_MAX_CHARS": "10"})
    assert choose_model("a" * 10, settings).reason == "simple"
    assert choose_model("a" * 10, settings).model == SMALL
    longer = choose_model("a" * 11, settings)
    assert (longer.model, longer.reason) == (LARGE, "long_question")


@pytest.mark.parametrize(
    ("size", "expected"),
    [(0, []), (2, ["m3", "m4"]), (9, ["m0", "m1", "m2", "m3", "m4"])],
)
def test_history_window_keeps_only_the_last_messages(size, expected):
    history = [{"role": "user", "content": f"m{index}"} for index in range(5)]
    kept = window_history(history, size)
    assert [message["content"] for message in kept] == expected
