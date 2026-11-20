"""Pasos de los escenarios de ``features/production_ready.feature``."""

import io

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import load_settings
from app.gateway import GatewayModel

scenarios("features/production_ready.feature")

API_KEY = "clave-de-prueba-0123456789"
SAFE_MESSAGE = "No pude generar una respuesta segura. Intenta de nuevo."
SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
AUTH = {"X-API-Key": API_KEY}


@pytest.fixture
def context():
    """Estado compartido entre los pasos de un escenario."""
    return {
        "env": {"MODEL_PROVIDER": "fake", "API_KEYS": f"tester:{API_KEY}"},
        "model": None,
        "client": None,
        "log": io.StringIO(),
        "gateway_calls": 0,
    }


def _events(context, log_lines, name):
    """Líneas del log con el evento ``name``."""
    return [line for line in log_lines(context["log"]) if line["event"] == name]


@given("the HR assistant runs with an API key and an observed log")
def runs_with_key(context):
    context["client"] = None


@given("a spy model that records the messages it receives")
def spy_model_given(context, spy_model):
    context["model"] = spy_model


@given(parsers.parse('a model that answers "{text}"'))
def model_answers(context, scripted_model, text):
    context["model"] = scripted_model(['{"answer": "%s"}' % text])


@given(
    parsers.parse(
        "a gateway that fails with 503 on every call and allows {retries:d} retries"
    )
)
def failing_gateway(context, gateway_env, retries):
    def handler(_request):
        context["gateway_calls"] += 1
        return httpx.Response(503, json={"error": "down"})

    settings = load_settings({**gateway_env, "MODEL_MAX_RETRIES": str(retries)})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    # La espera inyectada no duerme: el escenario corre al instante.
    context["model"] = GatewayModel(SMALL, settings, http, sleep=lambda _s: None)
    context["env"]["MODEL_MAX_RETRIES"] = str(retries)


@when(parsers.re(r'I ask "(?P<question>[^"]*)"$'))
def ask_question(context, scenario_client, question):
    client = scenario_client(context)
    context["response"] = client.post(
        "/ask", json={"question": question}, headers=AUTH
    )


@when(parsers.parse('I open "{path}" without a key'))
def open_without_key(context, scenario_client, path):
    context["response"] = scenario_client(context).get(path)


@when(parsers.parse('I open "{path}" with the key'))
def open_with_key(context, scenario_client, path):
    context["response"] = scenario_client(context).get(path, headers=AUTH)


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert context["response"].status_code == status


@then(
    parsers.parse(
        'the model received "{first}" and "{second}" instead of the real values'
    )
)
def model_got_masked_text(context, first, second):
    sent = context["model"].calls[0][-1]["content"]
    assert first in sent and second in sent
    assert "@example.com" not in sent and "GOMS800101AB1" not in sent


@then(
    parsers.parse(
        'the log has pii_detected lines for "{first}" and "{second}" on the input'
    )
)
def log_has_input_detections(context, log_lines, first, second):
    found = {
        line["pii_type"]: line
        for line in _events(context, log_lines, "pii_detected")
        if line["direction"] == "input"
    }
    assert {first, second} <= set(found)
    assert found[first]["count"] == 1


@then(parsers.parse('the log has pii_detected lines for "{kind}" on the output'))
def log_has_output_detection(context, log_lines, kind):
    lines = _events(context, log_lines, "pii_detected")
    assert any(
        line["pii_type"] == kind and line["direction"] == "output" for line in lines
    )


@then(parsers.parse('the log contains neither "{first}" nor "{second}"'))
def log_never_contains_two(context, first, second):
    text = context["log"].getvalue()
    assert first not in text and second not in text


@then(parsers.parse('the log never contains "{value}"'))
def log_never_contains(context, value):
    assert value not in context["log"].getvalue()


@then(parsers.parse('the answer contains "{kept}" and not "{removed}"'))
def answer_is_masked(context, kept, removed):
    answer = context["response"].json()["answer"]
    assert kept in answer and removed not in answer


@then("the answer is the safe message")
def answer_is_safe_message(context):
    assert context["response"].json()["answer"] == SAFE_MESSAGE


@then(parsers.parse('the log has an output_rejected line with the reason "{reason}"'))
def log_has_rejection(context, log_lines, reason):
    (line,) = _events(context, log_lines, "output_rejected")
    assert line["reason"] == reason


@then(parsers.parse("the gateway was called {count:d} times"))
def gateway_call_count(context, count):
    assert context["gateway_calls"] == count


@then("the page is HTML and does not contain the API key")
def page_is_public_html(context):
    response = context["response"]
    assert "text/html" in response.headers["content-type"]
    assert API_KEY not in response.text
