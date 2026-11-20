"""Pruebas unitarias de los reintentos del gateway (punto 3 del reto).

``GatewayModel`` recibe ``sleep`` por inyección: las pruebas anotan las esperas y
nunca duermen de verdad.
"""

import httpx
import pytest

from app.config import load_settings
from app.gateway import GatewayModel, ModelUnavailableError

SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
OK_BODY = {
    "choices": [{"message": {"content": '{"answer": "Hola."}'}}],
    "usage": {"prompt_tokens": 42, "completion_tokens": 7},
}
QUESTION = [{"role": "user", "content": "¿Quién es EMP-0004?"}]


class Flaky:
    """Transporte que responde con un guion y cuenta las llamadas.

    :param script: Respuestas o excepciones, una por llamada
    :type script: list
    """

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _model(flaky, env, sleeps):
    """``GatewayModel`` con transporte simulado y espera anotada en ``sleeps``."""
    client = httpx.Client(transport=httpx.MockTransport(flaky))
    return GatewayModel(SMALL, load_settings(env), client, sleep=sleeps.append)


def _ok():
    return httpx.Response(200, json=OK_BODY)


def test_timeouts_and_5xx_are_retried_with_exponential_waits(gateway_env):
    timeout = httpx.ReadTimeout("timed out", request=httpx.Request("POST", "http://x"))
    flaky = Flaky([timeout, httpx.Response(503), httpx.Response(500), _ok()])
    sleeps = []
    env = {**gateway_env, "MODEL_MAX_RETRIES": "3"}
    completion = _model(flaky, env, sleeps).complete(QUESTION)
    assert sleeps == [0.5, 1, 2]
    assert flaky.calls == 4
    assert (completion.input_tokens, completion.output_tokens) == (42, 7)


def test_a_4xx_error_is_never_retried(gateway_env):
    flaky = Flaky([httpx.Response(400, json={"error": "bad request"}), _ok()])
    sleeps = []
    with pytest.raises(ModelUnavailableError):
        _model(flaky, gateway_env, sleeps).complete(QUESTION)
    assert flaky.calls == 1
    assert not sleeps


def test_exhausted_retries_raise_without_leaking_the_token(gateway_env, token):
    flaky = Flaky([httpx.Response(503)] * 3)
    sleeps = []
    env = {**gateway_env, "MODEL_MAX_RETRIES": "2"}
    with pytest.raises(ModelUnavailableError) as error:
        _model(flaky, env, sleeps).complete(QUESTION)
    assert flaky.calls == 3
    assert sleeps == [0.5, 1]
    assert token not in str(error.value) and token not in repr(error.value)


def test_failed_attempts_do_not_add_to_the_cost_of_the_answer(
    make_client, gateway_env
):
    question = {"question": "¿Quién es EMP-0004?"}
    clean = _model(Flaky([_ok(), _ok()]), gateway_env, [])
    retried = _model(
        Flaky([httpx.Response(503), _ok(), httpx.Response(503), _ok()]),
        gateway_env,
        [],
    )
    clean_cost = make_client(model=clean).post("/ask", json=question).json()
    retried_cost = make_client(model=retried).post("/ask", json=question).json()
    assert clean_cost["cost_usd"] > 0
    assert retried_cost["cost_usd"] == clean_cost["cost_usd"]
