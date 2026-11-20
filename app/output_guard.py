"""Validación de la respuesta del modelo antes de devolverla (ADR 0014).

Devuelve solo el motivo del rechazo; el texto rechazado nunca se registra.
"""

import re

from app.directory import EmployeeDirectory
from app.pii import mask_pii

EMPLOYEE_ID = re.compile(r"\bEMP-\d{4}\b", re.IGNORECASE)
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


def _has_invented_id(
    answer: str, directory: EmployeeDirectory, asked: frozenset[str]
) -> bool:
    """Indica si la respuesta nombra un id ``EMP-xxxx`` que no está en el directorio.

    Un id que la persona escribió en su pregunta no cuenta como inventado: la
    respuesta puede decir que no existe.

    :param answer: Respuesta a revisar
    :type answer: str
    :param directory: Directorio de empleados
    :type directory: EmployeeDirectory
    :param asked: Ids (en mayúsculas) que trae la pregunta
    :type asked: frozenset[str]
    :return: ``True`` si algún id no existe ni venía en la pregunta
    :rtype: bool
    """
    return any(
        found.upper() not in asked and directory.get_employee(found) is None
        for found in EMPLOYEE_ID.findall(answer)
    )


def asked_ids(*texts: str) -> frozenset[str]:
    """Junta los ids ``EMP-xxxx`` que aparecen en los textos de la persona.

    :param texts: Pregunta e historial
    :type texts: str
    :return: Ids en mayúsculas
    :rtype: frozenset[str]
    """
    return frozenset(
        found.upper() for text in texts for found in EMPLOYEE_ID.findall(text)
    )


def rejection_reason(
    answer: str,
    max_chars: int,
    directory: EmployeeDirectory | None = None,
    asked: frozenset[str] = frozenset(),
) -> str | None:
    """Valida una respuesta.

    :param answer: Respuesta ya enmascarada
    :type answer: str
    :param max_chars: Largo máximo permitido
    :type max_chars: int
    :param directory: Directorio para comprobar ids; si falta no se comprueban
    :type directory: EmployeeDirectory | None
    :param asked: Ids que la persona ya nombró en su pregunta
    :type asked: frozenset[str]
    :return: ``None`` si es válida; si no, ``empty``, ``too_long``, ``pii``,
        ``secret`` o ``invented_id``
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
    if directory is not None and _has_invented_id(
        answer, directory, asked
    ):
        return "invented_id"
    return None
