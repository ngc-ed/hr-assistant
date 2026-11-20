"""Validación de la respuesta del modelo antes de devolverla (ADR 0014).

Devuelve solo el motivo del rechazo; el texto rechazado nunca se registra.
"""

import re

from app.pii import mask_pii

SAFE_ANSWER = "No pude generar una respuesta segura. Intenta de nuevo."
RANDOM_RUN_MIN_CHARS = 32
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
)
RANDOM_RUN = re.compile(r"[A-Za-z0-9_+/=-]{%d,}" % RANDOM_RUN_MIN_CHARS)


def _looks_random(run: str) -> bool:
    """Indica si una cadena larga mezcla letras y dígitos como una clave.

    :param run: Cadena sin espacios
    :type run: str
    :return: ``True`` si trae letras y dígitos
    :rtype: bool
    """
    return any(c.isalpha() for c in run) and any(c.isdigit() for c in run)


def _has_secret(answer: str) -> bool:
    """Indica si la respuesta parece traer una clave.

    :param answer: Respuesta a revisar
    :type answer: str
    :return: ``True`` si hay algo con forma de clave
    :rtype: bool
    """
    if any(pattern.search(answer) for pattern in SECRET_PATTERNS):
        return True
    return any(_looks_random(run) for run in RANDOM_RUN.findall(answer))


def rejection_reason(answer: str, max_chars: int) -> str | None:
    """Valida una respuesta.

    :param answer: Respuesta ya enmascarada
    :type answer: str
    :param max_chars: Largo máximo permitido
    :type max_chars: int
    :return: ``None`` si es válida; si no, ``empty``, ``too_long``, ``pii`` o
        ``secret``
    :rtype: str | None
    """
    if not answer.strip():
        return "empty"
    if len(answer) > max_chars:
        return "too_long"
    if mask_pii(answer)[1]:
        return "pii"
    if _has_secret(answer):
        return "secret"
    return None
