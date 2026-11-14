"""Pruebas unitarias del modelo real por AI Gateway, sin red (``MockTransport``)."""

import json

import httpx
import pytest

from app.config import load_settings
from app.gateway import GatewayModel, ModelUnavailableError
from app.llm import FakeModel, build_models

SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
EXPECTED_URL = (
    "https://gateway.ai.cloudflare.com/v1/cuenta-1/mi-gateway"
    "/workers-ai/v1/chat/completions"
)
OK_BODY = {
    "choices": [{"message": {"content": '{"answer": "Hola."}'}}],
    "usage": {"prompt_tokens": 42, "completion_tokens": 7},
}
QUESTION = [{"role": "user", "content": "¿Quién es EMP-0004?"}]


def _model(handler, env):
    """Crea un ``GatewayModel`` configurado con ``env`` que responde con ``handler``."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GatewayModel(SMALL, load_settings(env), client)


def test_gateway_posts_the_documented_request_and_reads_the_usage(gateway_env, token):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=OK_BODY)

    env = {**gateway_env, "MODEL_MAX_TOKENS": "120"}
    completion = _model(handler, env).complete(QUESTION)
    request = seen[0]
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == EXPECTED_URL
    assert request.headers["Authorization"] == f"Bearer {token}"
    assert "cf-aig-cache-ttl" not in request.headers
    assert set(body) == {"model", "messages", "max_tokens", "temperature"}
    assert (body["model"], body["max_tokens"], body["temperature"]) == (SMALL, 120, 0)
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1:] == QUESTION
    assert completion.text == '{"answer": "Hola."}'
    assert (completion.input_tokens, completion.output_tokens) == (42, 7)
    assert completion.cached is False


def test_cache_ttl_header_is_sent_and_a_hit_marks_the_call_as_cached(gateway_env):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200, json=OK_BODY, headers={"cf-aig-cache-status": "HIT"}
        )

    env = {**gateway_env, "CACHE_TTL_SECONDS": "60"}
    completion = _model(handler, env).complete(QUESTION)
    assert seen[0].headers["cf-aig-cache-ttl"] == "60"
    assert completion.cached is True


def _server_error(_request):
    return httpx.Response(500, json={"error": "boom"})


def _timeout(request):
    raise httpx.ReadTimeout("timed out", request=request)


def _invalid_json(_request):
    return httpx.Response(200, content=b"<html>no es json</html>")


def _missing_usage(_request):
    return httpx.Response(200, json={"choices": OK_BODY["choices"]})


@pytest.mark.parametrize(
    "handler", [_server_error, _timeout, _invalid_json, _missing_usage]
)
def test_gateway_failures_raise_model_unavailable_without_leaking_the_token(
    handler, gateway_env, token
):
    with pytest.raises(ModelUnavailableError) as error:
        _model(handler, gateway_env).complete(QUESTION)
    assert token not in str(error.value)
    assert token not in repr(error.value)


def test_build_models_creates_one_model_per_configured_name(directory, gateway_env):
    fake = build_models(load_settings({"MODEL_PROVIDER": "fake"}), directory)
    assert set(fake) == {SMALL, LARGE}
    assert all(isinstance(model, FakeModel) for model in fake.values())
    real = build_models(load_settings(gateway_env), directory)
    assert set(real) == {SMALL, LARGE}
    assert all(isinstance(model, GatewayModel) for model in real.values())
