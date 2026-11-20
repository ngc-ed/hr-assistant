"""Pruebas unitarias de la validación de salida (punto 2 del reto).

Contrato esperado: ``rejection_reason(answer, max_chars)`` devuelve ``None`` si la
respuesta es válida o el motivo: ``empty``, ``too_long``, ``pii`` o ``secret``.
"""

from app.output_guard import rejection_reason

MAX_CHARS = 50


def test_each_unsafe_answer_gets_its_own_reason():
    cases = {
        "empty": "   ",
        "too_long": "a " * (MAX_CHARS + 1),
        "pii": "Su correo es sofia.gomez@example.com",
        "secret": "La clave es sk-abcdefghijklmnopqrstuvwx",
    }
    reasons = {name: rejection_reason(text, MAX_CHARS) for name, text in cases.items()}
    assert reasons == {name: name for name in cases}


def test_other_key_shapes_are_rejected_as_secrets():
    bearer = "Authorization: Bearer abcdefghijklmnop12345"
    random_string = "x9Kq2LmZ7vB4nT8wR1yU5cD3fG6hJ0aS" * 2
    assert rejection_reason(bearer, 200) == "secret"
    assert rejection_reason(random_string, 200) == "secret"


def test_a_normal_answer_and_the_exact_limit_are_accepted():
    normal = "Según el directorio: Jorge Díaz (EMP-0004) trabaja en Tecnología."
    assert rejection_reason(normal, 200) is None
    assert rejection_reason("a" * MAX_CHARS, MAX_CHARS) is None
    assert rejection_reason("a" * (MAX_CHARS + 1), MAX_CHARS) == "too_long"
