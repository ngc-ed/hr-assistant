"""Pasos de los escenarios de ``features/web.feature``."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/web.feature")


@pytest.fixture
def context():
    """Estado compartido entre los pasos de un escenario."""
    return {}


@given("the HR assistant is running")
def assistant_is_running(context, make_client):
    context["client"] = make_client()


@when(parsers.parse('I open "{path}"'))
def open_path(context, path):
    context["response"] = context["client"].get(path)


@then(parsers.parse('the status is "{status}"'))
def status_is(context, status):
    assert context["response"].status_code == 200
    assert context["response"].json()["status"] == status


@then("the response includes the process id")
def includes_process_id(context):
    pid = context["response"].json()["pid"]
    assert isinstance(pid, int) and pid > 0


@then(parsers.parse('the page contains the test id "{test_id}"'))
def page_contains_test_id(context, test_id):
    assert context["response"].status_code == 200
    assert f'data-testid="{test_id}"' in context["response"].text
