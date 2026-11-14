"""Pasos de los escenarios de ``features/costs.feature``."""

import dataclasses
import io
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.gateway import ModelUnavailableError
from app.llm import FakeModel

scenarios("features/costs.feature")

PRICES_PATH = Path(__file__).resolve().parent.parent / "data" / "model_prices.json"


class UnavailableModel:
    """Modelo que siempre falla como si el gateway no respondiera."""

    def complete(self, messages):
        """Lanza el error del gateway en lugar de responder.

        :param messages: Conversación que recibe el modelo
        :type messages: list[dict]
        :raises ModelUnavailableError: Siempre
        """
        raise ModelUnavailableError()


class CachedModel:
    """Envuelve un modelo y marca cada respuesta como servida desde la caché.

    :param inner: Modelo al que se delega la respuesta
    :type inner: object
    """

    def __init__(self, inner):
        self.inner = inner

    def complete(self, messages):
        """Delega en el modelo interno y marca la respuesta como cacheada.

        :param messages: Conversación que recibe el modelo
        :type messages: list[dict]
        :return: La respuesta del modelo interno con ``cached=True``
        :rtype: Completion
        """
        return dataclasses.replace(self.inner.complete(messages), cached=True)


@pytest.fixture
def context():
    """Estado compartido entre los pasos de un escenario."""
    return {
        "env": {"MODEL_PROVIDER": "fake", "PRICES_PATH": str(PRICES_PATH)},
        "model": None,
        "client": None,
        "log": io.StringIO(),
    }


def _history(size):
    """Arma un historial alterno de ``size`` mensajes sin ids de empleado."""
    roles = ("user", "assistant")
    return [
        {"role": roles[index % 2], "content": f"mensaje {index}"}
        for index in range(size)
    ]


@given("the HR assistant runs with the simulated models and an observed log")
def runs_with_simulated_models(context):
    context["client"] = None


@given(parsers.parse("the router limit is {limit:d} characters"))
def router_limit(context, limit):
    context["env"]["ROUTER_MAX_CHARS"] = str(limit)


@given("routing is disabled")
def routing_disabled(context):
    context["env"]["ROUTING"] = "false"


@given(parsers.parse("the history window is {size:d} messages"))
def history_window(context, size):
    context["env"]["HISTORY_WINDOW"] = str(size)


@given("a spy model that counts the messages it receives")
def spy_counts_messages(context, spy_model):
    context["model"] = spy_model


@given("the model is unavailable")
def model_unavailable(context):
    context["model"] = UnavailableModel()


@given("a model whose every call is answered from the cache")
def model_from_cache(context, directory):
    context["model"] = CachedModel(FakeModel(directory.departments()))


@when(
    parsers.re(
        r'I ask "(?P<question>[^"]*)" with a history of (?P<size>\d+) messages'
    )
)
def ask_with_history(context, scenario_client, question, size):
    payload = {"question": question, "history": _history(int(size))}
    context["response"] = scenario_client(context).post("/ask", json=payload)


@when(parsers.re(r'I ask "(?P<question>[^"]*)"$'))
def ask_question(context, scenario_client, question):
    payload = {"question": question}
    context["response"] = scenario_client(context).post("/ask", json=payload)


@when(parsers.parse('I open "{path}"'))
def open_path(context, scenario_client, path):
    context["response"] = scenario_client(context).get(path)


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert context["response"].status_code == status


@then(
    parsers.parse('the answer used the model "{model}" with the route "{route}"')
)
def answer_used_model(context, model, route):
    body = context["response"].json()
    assert body["model"] == model
    assert body["route"] == route


@then("the answer cost is greater than zero")
def answer_cost_positive(context):
    body = context["response"].json()
    assert body["cost_usd"] > 0
    assert body["cached_calls"] == 0


@then(parsers.parse("the first model call receives {count:d} messages"))
def first_call_messages(context, count):
    first_call = context["model"].calls[0]
    assert len(first_call) == count
    assert first_call[0]["content"] == "mensaje 4"
    assert first_call[-1]["content"] == "¿Quién es EMP-0004?"


@then(
    parsers.parse(
        "the agent_run line records {received:d} history messages and {sent:d} sent"
    )
)
def agent_run_history(context, log_lines, received, sent):
    lines = log_lines(context["log"])
    (line,) = [line for line in lines if line["event"] == "agent_run"]
    assert line["history_messages"] == received
    assert line["history_sent"] == sent
    assert {"model", "route", "cached_calls", "cost_usd"} <= set(line)


@then("the metrics report a cost greater than zero")
def metrics_cost(context):
    assert context["response"].status_code == 200
    assert context["response"].json()["cost_usd"] > 0


@then(
    parsers.parse('the error body says "{detail}" with the response request id')
)
def error_body(context, detail):
    request_id = context["response"].headers["X-Request-ID"]
    assert context["response"].json() == {"detail": detail, "request_id": request_id}


@then(parsers.parse('the log has an error line of type "{error_type}"'))
def log_has_error(context, log_lines, error_type):
    (error,) = [line for line in log_lines(context["log"]) if line["event"] == "error"]
    assert error["error_type"] == error_type


@then("the answer has cached calls and costs zero")
def cached_answer_is_free(context):
    body = context["response"].json()
    assert body["cached_calls"] > 0
    assert body["cost_usd"] == 0
