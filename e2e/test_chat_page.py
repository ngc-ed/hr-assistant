"""Pruebas de punta a punta de la página del asistente (spec/04-production.md).

Se corren con pytest-playwright contra el producto vivo con el modelo simulado.
La URL base la pone la verificación con ``--base-url``.
"""

import os
import re

import pytest
from playwright.sync_api import Page, Route, expect

FIRST_QUESTION = "¿Quién es EMP-0004?"
SECOND_QUESTION = "¿Quién es EMP-0001?"
REQUEST_ID_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{7,}")
SPANISH_ERROR_PATTERN = re.compile(r"Escribe una pregunta", re.IGNORECASE)
WRONG_API_KEY = "wrong-key-for-e2e-0000"
ASSISTANT_PREFIX = "Asistente:"
API_ERROR_PATTERN = re.compile(r"error|no es válida|No se pudo conectar")


def _write_api_key(page: Page, api_key: str | None = None) -> None:
    """Escribe una clave en el campo api-key; falla con un mensaje claro.

    Sin ``api_key`` usa la variable ``E2E_API_KEY``.

    :param page: Página de Playwright con el producto abierto
    :type page: Page
    :param api_key: Clave a escribir; por omisión la de ``E2E_API_KEY``
    :type api_key: str | None
    :raises pytest.fail.Exception: Si falta ``E2E_API_KEY`` o el campo api-key
    """
    if api_key is None:
        api_key = os.environ.get("E2E_API_KEY")
        if not api_key:
            pytest.fail("The E2E_API_KEY environment variable is not set")
    field = page.get_by_test_id("api-key")
    expect(field, "The page has no field with data-testid=api-key").to_have_count(1)
    field.fill(api_key)


def _ask(page: Page, question: str) -> None:
    """Escribe una pregunta en la caja de texto y la envía.

    :param page: Página de Playwright con el producto abierto
    :type page: Page
    :param question: Texto de la pregunta
    :type question: str
    """
    page.get_by_test_id("question").fill(question)
    page.get_by_test_id("send").click()


def test_asking_a_question_shows_the_answer_and_its_request_id(page: Page) -> None:
    """Una pregunta enviada muestra la respuesta y su request_id."""
    page.goto("/")
    _write_api_key(page)
    _ask(page, FIRST_QUESTION)

    answer = page.get_by_test_id("answer")
    expect(answer).to_contain_text(FIRST_QUESTION)
    request_id = page.get_by_test_id("request-id")
    expect(request_id).to_have_count(1)
    expect(request_id).to_contain_text(REQUEST_ID_PATTERN)
    expect(answer).to_contain_text(ASSISTANT_PREFIX)
    expect(answer).not_to_contain_text(API_ERROR_PATTERN)


def test_sending_an_empty_question_shows_an_error_in_spanish(page: Page) -> None:
    """Una pregunta vacía muestra un mensaje de error en español y no llama a la API."""
    page.goto("/")
    page.get_by_test_id("question").fill("")
    page.get_by_test_id("send").click()

    expect(page.get_by_test_id("answer")).to_contain_text(SPANISH_ERROR_PATTERN)
    expect(page.get_by_test_id("request-id")).to_have_count(0)


def test_a_second_question_keeps_the_previous_conversation_on_screen(
    page: Page,
) -> None:
    """La segunda pregunta se agrega sin borrar la primera ni su respuesta."""
    page.goto("/")
    _write_api_key(page)
    _ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("request-id")).to_have_count(1)

    _ask(page, SECOND_QUESTION)
    expect(page.get_by_test_id("request-id")).to_have_count(2)

    answer = page.get_by_test_id("answer")
    expect(answer).to_contain_text(FIRST_QUESTION)
    expect(answer).to_contain_text(SECOND_QUESTION)


def test_valid_api_key_sends_question_shows_answer(page: Page) -> None:
    """Con clave API válida, la pregunta enviada muestra respuesta."""
    page.goto("/")
    _write_api_key(page)
    _ask(page, FIRST_QUESTION)

    answer = page.get_by_test_id("answer")
    expect(answer).to_contain_text(FIRST_QUESTION)
    expect(answer).to_contain_text(ASSISTANT_PREFIX)


def test_invalid_api_key_shows_error_401(page: Page) -> None:
    """Con clave API inválida, muestra «Clave inválida»."""
    page.goto("/")
    _write_api_key(page, WRONG_API_KEY)
    _ask(page, FIRST_QUESTION)

    error = page.get_by_test_id("error")
    expect(error).to_contain_text("Clave inválida")


def test_rate_limit_shows_error_429_with_retry_after(page: Page) -> None:
    """Exceder límite de peticiones muestra «Demasiadas preguntas; espera N segundos»."""
    retry_after_seconds = 7

    def reply_with_rate_limit(route: Route) -> None:
        route.fulfill(
            status=429,
            headers={"Retry-After": str(retry_after_seconds)},
            content_type="application/json",
            body='{"detail": "rate limit exceeded"}',
        )

    page.route("**/ask", reply_with_rate_limit)
    page.goto("/")
    _write_api_key(page)
    _ask(page, FIRST_QUESTION)

    expect(page.get_by_test_id("answer")).to_contain_text(
        f"Demasiadas preguntas; espera {retry_after_seconds} segundos"
    )
