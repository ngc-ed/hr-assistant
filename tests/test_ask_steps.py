"""Pasos de los escenarios de ``features/ask.feature``."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/ask.feature")


@pytest.fixture
def context():
    """Estado compartido entre los pasos de un escenario."""
    return {"env": {}, "model": None, "client": None, "responses": []}


def _client(context, make_client):
    """Crea el cliente una sola vez por escenario con lo que dijeron los ``Given``."""
    if context["client"] is None:
        context["client"] = make_client(env=context["env"], model=context["model"])
    return context["client"]


def _ask(context, make_client, body):
    response = _client(context, make_client).post("/ask", json=body)
    context["responses"].append(response)


@given("the HR assistant runs with the fake model")
def runs_with_fake_model(context):
    context["env"]["MODEL_PROVIDER"] = "fake"


@given("the model is observed by a spy")
def model_is_observed(context, spy_model):
    context["model"] = spy_model


@given(parsers.parse("the agent is limited to {steps:d} step"))
def agent_is_limited(context, steps):
    context["env"]["AGENT_MAX_STEPS"] = str(steps)


ASK_WITH_HISTORY = (
    r'I ask "(?P<question>[^"]*)" with the history "(?P<history>[^"]*)"'
)


@when(parsers.re(ASK_WITH_HISTORY))
def ask_with_history(context, make_client, question, history):
    body = {"question": question, "history": [{"role": "user", "content": history}]}
    _ask(context, make_client, body)


@when(parsers.re(r'I ask "(?P<question>[^"]*)"$'))
def ask_question(context, make_client, question):
    _ask(context, make_client, {"question": question})


@when(parsers.parse("I ask a question of {length:d} characters"))
def ask_long_question(context, make_client, length):
    _ask(context, make_client, {"question": "a" * length})


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert context["responses"][-1].status_code == status


@then(parsers.parse('the answer mentions "{text}"'))
def answer_mentions(context, text):
    assert text in context["responses"][-1].json()["answer"]


@then(parsers.parse('the answer is "{text}"'))
def answer_is(context, text):
    assert context["responses"][-1].json()["answer"] == text


@then(parsers.parse('the tools used are "{tools}"'))
def tools_used_are(context, tools):
    assert context["responses"][-1].json()["tools_used"] == tools.split(", ")


@then(parsers.parse("the number of steps is {steps:d}"))
def agent_took_steps(context, steps):
    assert context["responses"][-1].json()["steps"] == steps


@then(parsers.parse('the model never saw "{text}" in the second request'))
def model_never_saw(context, spy_model, text):
    assert all(response.status_code == 200 for response in context["responses"])
    first_call = spy_model.calls[0]
    assert first_call[0]["role"] == "system", "falta el prompt del especialista"
    assert first_call[1]["content"] == text, "la API no usó el historial"
    # The code runs the tool first, so the first request makes one model call.
    first_request_calls = 1
    later_calls = spy_model.calls[first_request_calls:]
    assert later_calls, "el modelo no recibió la segunda pregunta"
    for messages in later_calls:
        assert all(text not in message["content"] for message in messages)
