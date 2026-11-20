"""Guardián de entrada: bloquea la inyección de prompt con una lista de frases.

Corre antes del enmascarado de PII y de cualquier llamada al modelo. Devuelve solo la
frase que coincidió; el texto de la pregunta nunca sale de este módulo.
"""

import unicodedata

BLOCKED_MESSAGE = "La pregunta no se puede procesar."
BLOCKED_STATUS = 400
# Frases ya sin acentos y en minúsculas, que es como se comparan.
INJECTION_PHRASES: tuple[str, ...] = (
    "ignora tus instrucciones",
    "ignora las instrucciones",
    "ignora todas las instrucciones",
    "ignora las instrucciones anteriores",
    "olvida tus instrucciones",
    "olvida las instrucciones",
    "prompt del sistema",
    "prompt de sistema",
    "system prompt",
    "ignore previous instructions",
    "ignore your instructions",
    "actua como",
    "finge que eres",
    "modo desarrollador",
)


def _fold(text: str) -> str:
    """Pasa a minúsculas, quita acentos y junta los espacios.

    :param text: Texto original
    :type text: str
    :return: Texto normalizado para comparar
    :rtype: str
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.split())


def blocked_phrase(text: str) -> str | None:
    """Busca una frase de inyección de prompt en el texto.

    :param text: Pregunta (o turno del historial) sin enmascarar
    :type text: str
    :return: La frase de la lista que coincidió, o ``None`` si el texto pasa
    :rtype: str | None
    """
    folded = _fold(text)
    for phrase in INJECTION_PHRASES:
        if phrase in folded:
            return phrase
    return None
