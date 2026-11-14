"""Pruebas unitarias del modelo simulado (``FakeModel``)."""

import json

import pytest

from app.llm import FakeModel

TOOL_PREFIX = "Resultado de la herramienta: "


@pytest.fixture
def model():
    """Modelo simulado con los departamentos de los datos."""
    return FakeModel(["Tecnología", "Ventas", "Finanzas"])


def _reply(model, *contents):
    messages = [{"role": "user", "content": content} for content in contents]
    return json.loads(model.complete(messages).text)


def test_tool_result_becomes_an_answer_even_if_it_has_an_employee_id(model):
    result = '{"id": "EMP-0004", "name": "Jorge Díaz"}'
    reply = _reply(model, TOOL_PREFIX + result)
    assert reply == {"answer": "Según el directorio: " + result}


def test_employee_id_requests_get_employee(model):
    reply = _reply(model, "¿Quién es EMP-0004?")
    assert reply == {"tool": "get_employee", "args": {"employee_id": "EMP-0004"}}


def test_known_department_requests_search_by_department(model):
    reply = _reply(model, "¿Quiénes trabajan en finanzas?")
    assert reply["tool"] == "search_by_department"
    assert reply["args"]["department"].lower() == "finanzas"


def test_other_question_gets_the_help_answer(model):
    reply = _reply(model, "¿Qué hora es?")
    expected = "Pregúntame por un empleado (EMP-0001) o un departamento."
    assert reply == {"answer": expected}


def test_tokens_are_counted_as_words(model):
    messages = [
        {"role": "user", "content": "uno dos"},
        {"role": "assistant", "content": "tres cuatro cinco"},
    ]
    completion = model.complete(messages)
    assert completion.input_tokens == 5
    assert completion.output_tokens == len(completion.text.split())
