"""Palancas de costo: enrutamiento por regla y ventana de historial (ADR 0007)."""

from dataclasses import dataclass

from app.config import Settings

COMPLEX_KEYWORDS = ("compara", "resume", "explica", "por qué", "analiza", "todos")
REASON_ROUTING_DISABLED = "routing_disabled"
REASON_LONG_QUESTION = "long_question"
REASON_KEYWORD_PREFIX = "keyword:"
REASON_SIMPLE = "simple"


@dataclass(frozen=True)
class Route:
    """Modelo elegido para una pregunta y el motivo de la elección.

    :param model: Nombre del modelo elegido
    :type model: str
    :param reason: Motivo del enrutador (por ejemplo ``simple``)
    :type reason: str
    """

    model: str
    reason: str


def choose_model(question: str, settings: Settings) -> Route:
    """Elige el modelo con una regla en código, sin llamar a otro modelo.

    El orden es: enrutamiento apagado, pregunta larga, palabra clave y, si no,
    el modelo barato.

    :param question: Pregunta de la persona
    :type question: str
    :param settings: Configuración con modelos y palancas
    :type settings: Settings
    :return: El modelo elegido y el motivo
    :rtype: Route
    """
    if not settings.routing:
        return Route(settings.model_large, REASON_ROUTING_DISABLED)
    if len(question) > settings.router_max_chars:
        return Route(settings.model_large, REASON_LONG_QUESTION)
    folded = question.casefold()
    for keyword in COMPLEX_KEYWORDS:
        if keyword in folded:
            return Route(settings.model_large, REASON_KEYWORD_PREFIX + keyword)
    return Route(settings.model_small, REASON_SIMPLE)


def window_history(history: list[dict], size: int) -> list[dict]:
    """Devuelve solo los últimos ``size`` mensajes del historial.

    :param history: Turnos anteriores con ``role`` y ``content``
    :type history: list[dict]
    :param size: Cuántos mensajes conservar (``0`` deja la lista vacía)
    :type size: int
    :return: Los últimos mensajes, en su orden original
    :rtype: list[dict]
    """
    if size <= 0:
        return []
    return list(history[-size:])
