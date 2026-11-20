"""Steps for the scenarios in ``features/multiagent.feature``."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/multiagent.feature")


@pytest.fixture
def context():
    """State shared between the steps of one scenario."""
    return {}


@given("an assistant with a spy model")
def _assistant(context, make_client, spy_model):
    context["model"] = spy_model
    context["client"] = make_client(model=spy_model)


@when(parsers.parse('I ask "{question}"'))
def _ask(context, question):
    context["response"] = context["client"].post("/ask", json={"question": question})


@then(parsers.parse("the response status is {status:d}"))
def _status(context, status):
    assert context["response"].status_code == status


@then("the response says the question cannot be processed")
def _blocked_message(context):
    assert "La pregunta no se puede procesar." in context["response"].text


@then("the model received no calls")
def _no_calls(context):
    assert not context["model"].calls


@then(parsers.parse('the specialist is "{specialist}"'))
def _specialist(context, specialist):
    assert context["response"].json()["specialist"] == specialist


@then(parsers.parse('the stages are "{stages}"'))
def _stages(context, stages):
    assert context["response"].json()["agents"] == stages.split(", ")
