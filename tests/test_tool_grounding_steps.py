"""Steps for the scenarios in ``features/tool_grounding.feature``."""

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import load_settings
from app.llm import build_models

EMPLOYEES_PATH = Path(__file__).resolve().parent.parent / "data" / "employees.json"

scenarios("features/tool_grounding.feature")


@pytest.fixture
def context():
    """State shared between the steps of one scenario."""
    return {}


@given("an assistant whose model never asks for tools")
def _assistant(context, make_client, directory):
    env = {"MODEL_PROVIDER": "fake", "FAKE_MODEL_MODE": "no_tools"}
    settings = load_settings({"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **env})
    model = build_models(settings, directory)[settings.model_small]
    # Precondition: the simulated model really is in no_tools mode.
    probe = model.complete([{"role": "user", "content": "EMP-0004"}]).text
    assert '"tool"' not in probe
    context["client"] = make_client(env=env, model=model)


@when(parsers.parse('I ask "{question}"'))
def _ask(context, question):
    context["response"] = context["client"].post("/ask", json={"question": question})


@then(parsers.parse("the response status is {status:d}"))
def _status(context, status):
    assert context["response"].status_code == status


@then(parsers.parse('the tools used include "{tool}"'))
def _tool_used(context, tool):
    assert tool in context["response"].json()["tools_used"]


@then(parsers.parse('the answer does not mention "{text}"'))
def _answer_without(context, text):
    assert text not in context["response"].json()["answer"]
