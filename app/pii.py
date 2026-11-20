"""Detección y enmascarado de datos personales (ADR 0013).

Solo devuelve texto enmascarado y conteos por tipo: el valor detectado nunca sale de
este módulo, así que no puede llegar al log, a la traza ni a un mensaje de error.
"""

import re

# El orden importa: lo más específico va primero para que un CURP no se lea como RFC
# y una tarjeta de 16 dígitos no se lea como NSS o teléfono.
PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("CORREO", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
    (
        "CURP",
        re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.IGNORECASE),
    ),
    ("RFC", re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)),
    ("TARJETA", re.compile(r"(?<!\d)\d{16}(?!\d)")),
    ("NSS", re.compile(r"(?<!\d)\d{11}(?!\d)")),
    ("TELEFONO", re.compile(r"(?<!\d)\d{10}(?!\d)")),
)


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Cambia cada dato personal por su etiqueta (``[CORREO]``, ``[RFC]``...).

    :param text: Texto a revisar
    :type text: str
    :return: El texto enmascarado y los conteos por tipo (sin valores)
    :rtype: tuple[str, dict[str, int]]
    """
    counts: dict[str, int] = {}
    for kind, pattern in PII_PATTERNS:
        text, found = pattern.subn(f"[{kind}]", text)
        if found:
            counts[kind] = found
    return text, counts
