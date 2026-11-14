"""Pasos de los escenarios de ``features/observability.feature``."""

import io
import uuid

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/observability.feature")

INVALID_REQUEST_IDS = {
    "spaced": "id con espacios",
    "too long": "a" * 200,
}


class FailingModel:
    """Modelo que siempre lanza ``RuntimeError`` con un mensaje secreto.

    :param message: Mensaje del error, que nunca debe llegar al log
    :type message: str
    """

    def __init__(self, message):
        self.message = message

    def complete(self, messages):
        """Lanza el error en lugar de responder.

        :param messages: Conversación que recibe el modelo
        :type messages: list[dict]
        :raises RuntimeError: Siempre
        """
        raise RuntimeError(self.message)


@pytest.fixture
def context():
    """Estado compartido entre los pasos de un escenario."""
    return {
        "env": {"MODEL_PROVIDER": "fake"},
        "model": None,
        "client": None,
        "log": io.StringIO(),
        "question": None,
    }


def _response_request_id(context):
    return context["response"].headers["X-Request-ID"]


@given("the HR assistant runs with an observed log")
def runs_with_observed_log(context):
    context["client"] = None


@given(parsers.parse('the model fails with the message "{message}"'))
def model_fails(context, message):
    context["model"] = FailingModel(message)


@when(parsers.re(r'I open "(?P<path>[^"]*)"$'))
def open_path(context, scenario_client, path):
    context["response"] = scenario_client(context).get(path)


@when(
    parsers.parse('I open "{path}" with an invalid request id that is {kind}')
)
def open_with_invalid_id(context, scenario_client, path, kind):
    headers = {"X-Request-ID": INVALID_REQUEST_IDS[kind]}
    context["response"] = scenario_client(context).get(path, headers=headers)


@when(
    parsers.re(
        r'I ask "(?P<question>[^"]*)" with the request id "(?P<request_id>[^"]*)"'
    )
)
def ask_with_request_id(context, scenario_client, question, request_id):
    context["question"] = question
    context["response"] = scenario_client(context).post(
        "/ask", json={"question": question}, headers={"X-Request-ID": request_id}
    )


@when(parsers.re(r'I ask "(?P<question>[^"]*)"$'))
def ask_question(context, scenario_client, question):
    context["question"] = question
    payload = {"question": question}
    context["response"] = scenario_client(context).post("/ask", json=payload)


@then("the response header X-Request-ID is a valid UUID")
def header_is_uuid(context):
    value = _response_request_id(context)
    assert str(uuid.UUID(value)) == value


@then(parsers.parse('the response header X-Request-ID is "{request_id}"'))
def header_is(context, request_id):
    assert _response_request_id(context) == request_id


@then(parsers.parse('the response body has the request id "{request_id}"'))
def body_has_request_id(context, request_id):
    assert context["response"].json()["request_id"] == request_id


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert context["response"].status_code == status


@then(parsers.parse('the log has a "{event}" line with the response request id'))
@then(parsers.parse('the log has an "{event}" line with the response request id'))
def log_has_event(context, log_lines, event):
    lines = [line for line in log_lines(context["log"]) if line["event"] == event]
    assert lines, f"no hay líneas {event} en el log"
    assert all(line["request_id"] == _response_request_id(context) for line in lines)
    for line in lines:
        assert {"ts", "service", "event", "request_id"} <= set(line)


@then("the agent_run line counts the question without its text")
def agent_run_counts(context, log_lines):
    lines = log_lines(context["log"])
    (line,) = [line for line in lines if line["event"] == "agent_run"]
    assert line["question_chars"] == len(context["question"])
    assert line["history_messages"] == 0
    assert line["tools"] == ["get_employee"]
    assert line["stopped"] is False
    assert line["input_tokens"] > 0 and line["output_tokens"] > 0


@then("no log line contains the question or the answer")
def log_has_no_text(context):
    log = context["log"].getvalue()
    assert context["question"] not in log
    assert context["response"].json()["answer"] not in log


@then(
    parsers.parse(
        'the log has an audit line for "{tool}" with employee id "{employee_id}"'
    )
)
def log_has_audit(context, log_lines, tool, employee_id):
    (audit,) = [line for line in log_lines(context["log"]) if line["event"] == "audit"]
    assert audit["action"] == "tool_call"
    assert audit["tool"] == tool
    assert audit["args"] == {"employee_id": employee_id}
    assert audit["request_id"] == _response_request_id(context)


@then(
    parsers.parse(
        'the error body says "{detail}" with the response request id'
    )
)
def error_body(context, detail):
    assert context["response"].json() == {
        "detail": detail,
        "request_id": _response_request_id(context),
    }


@then(parsers.parse('the log has an error line of type "{error_type}"'))
def log_has_error(context, log_lines, error_type):
    errors = [line for line in log_lines(context["log"]) if line["event"] == "error"]
    assert [error["error_type"] for error in errors] == [error_type]
    assert errors[0]["request_id"] == _response_request_id(context)


@then(parsers.parse('no log line contains "{text}"'))
def log_does_not_contain(context, text):
    assert text not in context["log"].getvalue()


@then(parsers.parse("the metrics count at least {count:d} request"))
def metrics_count(context, count):
    assert context["response"].status_code == 200
    assert context["response"].json()["requests"] >= count


@then("the metrics report input tokens")
def metrics_tokens(context):
    assert context["response"].json()["tokens"]["input"] > 0


@then("the metrics report p50 and p95 latency")
def metrics_latency(context):
    latency = context["response"].json()["latency_ms"]
    assert latency["p50"] > 0
    assert latency["p95"] >= latency["p50"]


@then("the metrics say whether the SLO is met")
def metrics_slo(context):
    slo = context["response"].json()["slo"]
    assert slo["p95_ms_target"] == 2000
    assert isinstance(slo["met"], bool)


@then(parsers.parse('the page contains the text "{text}"'))
def page_contains_text(context, text):
    assert context["response"].status_code == 200
    assert text in context["response"].text


@then(parsers.parse('the page contains the test id "{test_id}"'))
def page_contains_test_id(context, test_id):
    assert f'data-testid="{test_id}"' in context["response"].text
