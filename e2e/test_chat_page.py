"""Pruebas de punta a punta del asistente (spec/04 y spec/05-production-ready.md).

Se corren con pytest-playwright contra el producto vivo con el modelo simulado.
La URL base la pone la verificación con ``--base-url``.

Los data-testid del tablero no están definidos en la especificación; se usan
``api-key`` (la misma clave de la página principal), ``requests`` y
``error-rate``.
"""

import os
import re

import pytest
from playwright.sync_api import Page, Route, expect

FIRST_QUESTION = "¿Quién es EMP-0004?"
EMAIL_ADDRESS = "persona.prueba@example.com"
EMAIL_QUESTION = f"Mi correo es {EMAIL_ADDRESS}, ¿quién es EMP-0004?"
REQUEST_ID_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{7,}")
WRONG_API_KEY = "wrong-key-for-e2e-0000"
ASSISTANT_PREFIX = "Asistente:"
API_ERROR_PATTERN = re.compile(r"error|no es válida|No se pudo conectar")
DIGIT_PATTERN = re.compile(r"\d")


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


def test_invalid_api_key_shows_error_401(page: Page) -> None:
    """Con clave API inválida, muestra «Clave inválida»."""
    page.goto("/")
    _write_api_key(page, WRONG_API_KEY)
    _ask(page, FIRST_QUESTION)

    expect(page.get_by_test_id("error")).to_contain_text("Clave inválida")


def test_rate_limit_shows_error_429_with_retry_after(page: Page) -> None:
    """Un 429 muestra «Demasiadas preguntas; espera N segundos»."""
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


def test_dashboard_opens_without_key_and_shows_figures_after_typing_it(
    page: Page,
) -> None:
    """El tablero abre sin clave y, con la clave, muestra peticiones y error_rate."""
    response = page.goto("/dashboard")
    assert response is not None and response.status == 200

    _write_api_key(page)

    expect(page.get_by_test_id("requests")).to_contain_text(DIGIT_PATTERN)
    expect(page.get_by_test_id("error-rate")).to_contain_text(DIGIT_PATTERN)


def test_dashboard_without_key_shows_no_figures(page: Page) -> None:
    """Sin clave, el tablero no muestra cifras de peticiones ni de error_rate."""
    page.goto("/dashboard")
    page.evaluate("sessionStorage.clear()")
    page.reload()

    expect(page.get_by_test_id("requests")).not_to_contain_text(DIGIT_PATTERN)
    expect(page.get_by_test_id("error-rate")).not_to_contain_text(DIGIT_PATTERN)


def test_a_question_with_an_email_does_not_show_it_on_the_page(page: Page) -> None:
    """Una pregunta con un correo no deja el correo visible en la página."""
    page.goto("/")
    _write_api_key(page)
    _ask(page, EMAIL_QUESTION)

    # La página repite lo que escribió la persona («Tú: ...»); se revisa solo
    # el mensaje del asistente (la página no le da data-testid propio).
    assistant_reply = page.get_by_test_id("answer").locator(".assistant")
    expect(page.get_by_test_id("request-id")).to_have_count(1)
    expect(assistant_reply).to_have_count(1)
    expect(assistant_reply).to_contain_text(ASSISTANT_PREFIX)
    expect(assistant_reply).not_to_contain_text(EMAIL_ADDRESS)
