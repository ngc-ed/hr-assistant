"""Pasos de los escenarios de ``features/production.feature``."""

import io
import json
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import load_settings
from app.main import create_app

EMPLOYEES_PATH = Path(__file__).resolve().parent.parent / "data" / "employees.json"

scenarios("features/production.feature")

ALICE_KEY = "secretkey123456"
BOB_KEY = "anothersecret123"


class ManualClock:
    """Reloj inyectado que solo avanza cuando el escenario lo pide.

    :param now: Hora que devuelve ``now()``
    :type now: datetime
    """

    def __init__(self, now):
        self._now = now
        self._ticks = 1000.0

    def now(self):
        """Devuelve la hora fija."""
        return self._now

    def monotonic(self):
        """Devuelve el contador actual sin avanzarlo."""
        return self._ticks

    def advance(self, seconds):
        """Avanza el contador ``seconds`` segundos."""
        self._ticks += seconds


@pytest.fixture
def context(fixed_clock):
    """Estado compartido entre los pasos de un escenario."""
    return {
        "env": {},
        "model": None,
        "client": None,
        "responses": [],
        "api_keys_config": f"alice:{ALICE_KEY},bob:{BOB_KEY}",
        "log_stream": None,
        "app": None,
        "clock": ManualClock(fixed_clock.now()),
    }


def _client(context, make_client):
    """Crea el cliente una sola vez por escenario."""
    if context["client"] is None:
        context["log_stream"] = io.StringIO()
        context["client"] = make_client(
            env=context["env"],
            model=context["model"],
            clock=context["clock"],
            log_stream=context["log_stream"],
        )
    return context["client"]


@when(parsers.parse('I send 1 more request to "{endpoint}" with the same key'))
def send_one_more_request(context, make_client, endpoint):
    """Send one more request with the first client's key."""
    response = _client(context, make_client).post(
        endpoint,
        json={"question": "¿Quién es EMP-0004?"},
        headers={"X-API-Key": ALICE_KEY},
    )
    context["responses"].append(response)


@when(parsers.parse("the clock advances {seconds:d} seconds"))
def clock_advances(context, seconds):
    """Advance the injected clock."""
    context["clock"].advance(seconds)


@then(parsers.parse("the request number {number:d} returns {status:d}"))
def request_number_returns(context, number, status):
    """Check the status of the Nth request of the scenario."""
    assert context["responses"][number - 1].status_code == status


@then(parsers.parse('the "{event}" log event has the client "{client_name}"'))
def log_event_has_client(context, event, client_name):
    """Check that every log line of the event carries the client name."""
    lines = [
        json.loads(line)
        for line in context["log_stream"].getvalue().splitlines()
        if line
    ]
    events = [line for line in lines if line["event"] == event]
    assert events, f"no {event} events in the log"
    assert all(line.get("client") == client_name for line in events)


@given("the HR assistant runs with the fake model")
def runs_with_fake_model(context):
    context["env"]["MODEL_PROVIDER"] = "fake"


@given("API keys are configured for two clients")
def api_keys_configured(context):
    context["env"]["API_KEYS"] = context["api_keys_config"]


@given(parsers.parse("the rate limit is set to {limit:d} requests per minute"))
def rate_limit_configured(context, limit):
    context["env"]["RATE_LIMIT_PER_MINUTE"] = str(limit)


@when(
    parsers.re(
        r'I ask "(?P<question>[^"]*)" with a valid API key'
    )
)
def ask_with_valid_key(context, make_client, question):
    """Ask a question using the first valid API key."""
    if context["client"] is None:
        _client(context, make_client)

    api_key = "secretkey123456"
    response = context["client"].post(
        "/ask",
        json={"question": question},
        headers={"X-API-Key": api_key},
    )
    context["responses"].append(response)


@when(parsers.parse('I send a request to "{endpoint}" with an invalid API key'))
def send_request_invalid_key(context, make_client, endpoint):
    """Send a request with an invalid API key."""
    if context["client"] is None:
        _client(context, make_client)

    response = context["client"].post(
        endpoint,
        json={"question": "test"},
        headers={"X-API-Key": "invalid-key"},
    )
    context["responses"].append(response)


@when(parsers.parse('I send a request to "{endpoint}" without the API key header'))
def send_request_no_key(context, make_client, endpoint):
    """Send a request without the API key header."""
    if context["client"] is None:
        _client(context, make_client)

    response = context["client"].post(
        endpoint,
        json={"question": "test"},
    )
    context["responses"].append(response)


@when(parsers.parse('I send a GET request to "{endpoint}" without the API key header'))
def send_get_request_no_key(context, make_client, endpoint):
    """Send a GET request without the API key header."""
    if context["client"] is None:
        _client(context, make_client)

    response = context["client"].get(endpoint)
    context["responses"].append(response)


@when(parsers.parse('I send a GET request to "{endpoint}" with a valid API key'))
def send_get_request_with_key(context, make_client, endpoint):
    """Send a GET request with a valid API key."""
    if context["client"] is None:
        _client(context, make_client)

    api_key = "secretkey123456"
    response = context["client"].get(
        endpoint,
        headers={"X-API-Key": api_key},
    )
    context["responses"].append(response)


@when(
    parsers.parse("I send {count:d} requests to \"{endpoint}\" "
                  "with a valid API key within {seconds:d} seconds")
)
def send_multiple_requests_fast(context, make_client, count, endpoint):
    """Send multiple requests quickly."""
    if context["client"] is None:
        _client(context, make_client)

    api_key = "secretkey123456"
    for _ in range(count):
        response = context["client"].post(
            endpoint,
            json={"question": "¿Quién es EMP-0004?"},
            headers={"X-API-Key": api_key},
        )
        context["responses"].append(response)


@when(
    parsers.parse("I try to start the app with ENVIRONMENT set to {environment}")
)
def try_start_with_environment(context, environment):
    """Attempt to start the app with a specific environment."""
    context["env"]["ENVIRONMENT"] = environment
    context["should_fail"] = False


@when("API_KEYS is empty")
def set_empty_api_keys(context):
    """Set API_KEYS to empty string."""
    context["env"]["API_KEYS"] = ""


@when("API_KEYS contains a key shorter than 16 characters")
def set_short_api_keys(context):
    """Set API_KEYS with a short key."""
    context["env"]["API_KEYS"] = "client:short,other:alsoashortkey"


@when("API_KEYS contains valid 16-character keys")
def set_valid_api_keys(context):
    """Set API_KEYS with valid keys."""
    context["env"]["API_KEYS"] = "client:1234567890123456,other:abcdefghijklmnop"


@when("MODEL_PROVIDER is set to fake")
def set_fake_model_provider(context):
    """Set MODEL_PROVIDER to fake."""
    context["env"]["MODEL_PROVIDER"] = "fake"


@when("MODEL_PROVIDER is not fake")
def set_real_model_provider(context):
    """Set MODEL_PROVIDER to something other than fake."""
    context["env"]["MODEL_PROVIDER"] = "gateway"
    context["env"]["CF_ACCOUNT_ID"] = "account-123"
    context["env"]["CF_GATEWAY_ID"] = "gateway-123"
    context["env"]["CF_API_TOKEN"] = "token-xyz"


@when("tracing is enabled")
def enable_tracing(context):
    """Enable tracing."""
    context["env"]["LANGSMITH_API_KEY"] = "ls-key-123"


@when("HIDE_INPUTS is set to false")
def set_hide_inputs_false(context):
    """Set HIDE_INPUTS to false."""
    context["env"]["HIDE_INPUTS"] = "false"


@when("HIDE_INPUTS is true")
def set_hide_inputs_true(context):
    """Set HIDE_INPUTS to true."""
    context["env"]["HIDE_INPUTS"] = "true"


@when("HIDE_OUTPUTS is set to false")
def set_hide_outputs_false(context):
    """Set HIDE_OUTPUTS to false."""
    context["env"]["HIDE_OUTPUTS"] = "false"


@when("HIDE_OUTPUTS is true")
def set_hide_outputs_true(context):
    """Set HIDE_OUTPUTS to true."""
    context["env"]["HIDE_OUTPUTS"] = "true"


@when(
    parsers.parse(
        'I send a request to "{endpoint}" with a valid API key '
        'for client "{client_name}"'
    )
)
def send_request_for_client(context, make_client, endpoint, client_name):
    """Send a request with a specific client's API key."""
    if context["client"] is None:
        _client(context, make_client)

    api_key = "secretkey123456" if client_name == "alice" else "anothersecret123"
    response = context["client"].post(
        endpoint,
        json={"question": "¿Quién es EMP-0004?"},
        headers={"X-API-Key": api_key},
    )
    context["responses"].append(response)
    context["current_client"] = client_name


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    """Check the last response status code."""
    assert context["responses"][-1].status_code == status


@then(parsers.parse('the response detail is "{detail}"'))
def response_detail_is(context, detail):
    """Check the detail field in the response."""
    response_data = context["responses"][-1].json()
    assert response_data.get("detail") == detail


@then(parsers.parse('the answer mentions "{text}"'))
def answer_mentions(context, text):
    """Check that the answer contains specific text."""
    assert text in context["responses"][-1].json()["answer"]


@then("the first 2 requests succeed")
def first_two_requests_succeed(context):
    """Check that the first 2 requests succeeded."""
    for i in range(2):
        assert context["responses"][i].status_code == 200


@then("the first 3 requests succeed")
def first_requests_succeed(context):
    """Check that the first 3 requests succeeded."""
    for i in range(3):
        assert context["responses"][i].status_code == 200


@then("the 4th request returns 429")
def fourth_request_rate_limited(context):
    """Check that the 4th request was rate limited."""
    assert context["responses"][3].status_code == 429


@then("the 3rd request returns 429")
def third_request_rate_limited(context):
    """Check that the 3rd request was rate limited."""
    assert context["responses"][2].status_code == 429


@then(parsers.parse('the "{header}" header is set to a positive integer'))
def check_retry_after_header(context, header):
    """Check that Retry-After header is set to a positive integer."""
    response = context["responses"][-1]
    assert header in response.headers
    retry_after = response.headers[header]
    assert int(retry_after) > 0


@then("all requests succeed with status 200")
def all_requests_succeed(context):
    """Check that all requests succeeded."""
    for response in context["responses"]:
        assert response.status_code == 200


@then("the app fails to start")
def app_fails_to_start(context, make_client):
    """Verify that the app fails to start with the given configuration."""
    with pytest.raises(ValueError):
        _client(context, make_client)


@then("the app starts successfully")
def app_starts_successfully(context, make_client):
    """Verify that the app starts with the given configuration."""
    _client(context, make_client)
    assert context["client"] is not None


@then(parsers.parse('the error message does not expose {what}'))
def error_message_safe(context, what):
    """Verify that error messages don't expose sensitive information."""
    with pytest.raises(ValueError) as exc_info:
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **context["env"]}
        settings = load_settings(variables)
        create_app(settings=settings)

    error_str = str(exc_info.value)
    if what == "the empty value":
        assert "" not in error_str or "empty" in error_str.lower()
    elif what == "the actual key":
        assert "secret" not in error_str.lower()


@then("the request succeeds")
def request_succeeds(context):
    """Check that the last request succeeded."""
    assert context["responses"][-1].status_code == 200


@then(parsers.parse('the log contains the client name "{client_name}"'))
def log_contains_client_name(context, client_name):
    """Check that the log contains the client name."""
    if context["log_stream"]:
        log_content = context["log_stream"].getvalue()
        log_lines = [json.loads(line) for line in log_content.splitlines() if line]
        assert any(
            log_entry.get("client") == client_name for log_entry in log_lines
        )


@then("the log does not contain the API key")
def log_does_not_contain_key(context):
    """Check that the log does not contain the API key."""
    log_content = context["log_stream"].getvalue()
    assert log_content, "the log is empty"
    assert ALICE_KEY not in log_content
    assert BOB_KEY not in log_content
