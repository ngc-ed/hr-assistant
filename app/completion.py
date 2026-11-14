"""Respuesta de un modelo, compartida por el simulado y el real (ADR 0002)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Completion:
    """Respuesta de un modelo.

    :param text: Texto devuelto por el modelo (un objeto JSON)
    :type text: str
    :param input_tokens: Tokens de entrada consumidos
    :type input_tokens: int
    :param output_tokens: Tokens de salida generados
    :type output_tokens: int
    :param cached: ``True`` si la respuesta salió de la caché del gateway
    :type cached: bool
    """

    text: str
    input_tokens: int
    output_tokens: int
    cached: bool = False
