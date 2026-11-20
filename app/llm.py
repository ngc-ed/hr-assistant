"""Interfaz del modelo de lenguaje y modelo simulado (ADR 0002)."""

import json
import re
import time
from collections.abc import Callable
from typing import Protocol

from app.completion import Completion
from app.config import GATEWAY_PROVIDER, Settings
from app.directory import EmployeeDirectory
from app.gateway import GatewayModel, create_http_client

__all__ = [
    "Completion",
    "FakeModel",
    "LanguageModel",
    "build_models",
    "TOOL_RESULT_PREFIX",
]

TOOL_RESULT_PREFIX = "Resultado de la herramienta: "
HELP_ANSWER = "Pregúntame por un empleado (EMP-0001) o un departamento."
EMPLOYEE_ID_PATTERN = re.compile(r"EMP-\d{4}", re.IGNORECASE)
FAKE_PROVIDER = "fake"


class LanguageModel(Protocol):
    """Protocolo que debe cumplir cualquier modelo que use el agente."""

    def complete(self, messages: list[dict]) -> Completion:
        """Genera la siguiente respuesta de la conversación.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: list[dict]
        :return: La respuesta del modelo
        :rtype: Completion
        """


def _count_words(text: str) -> int:
    """Cuenta palabras separadas por espacios.

    :param text: Texto a contar
    :type text: str
    :return: Número de palabras
    :rtype: int
    """
    return len(text.split())


class FakeModel:
    """Modelo simulado, determinista y sin red.

    Su nombre decide el precio: dos simulados con los nombres de ``MODEL_SMALL`` y
    ``MODEL_LARGE`` responden igual pero cuestan distinto.

    :param departments: Departamentos que existen en los datos
    :type departments: list[str]
    :param name: Nombre del modelo (para buscar su precio)
    :type name: str
    """

    def __init__(self, departments: list[str], name: str = FAKE_PROVIDER):
        self._departments = tuple(departments)
        self.name = name

    def complete(self, messages: list[dict]) -> Completion:
        """Decide con reglas sobre el último mensaje.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: list[dict]
        :return: Un objeto JSON con ``tool`` y ``args`` o con ``answer``
        :rtype: Completion
        """
        last = messages[-1]["content"] if messages else ""
        reply = self._decide(last)
        text = json.dumps(reply, ensure_ascii=False)
        input_tokens = sum(_count_words(m.get("content", "")) for m in messages)
        return Completion(
            text=text, input_tokens=input_tokens, output_tokens=_count_words(text)
        )

    def _decide(self, last: str) -> dict:
        """Aplica las cuatro reglas de la especificación en orden.

        :param last: Contenido del último mensaje
        :type last: str
        :return: La respuesta como diccionario
        :rtype: dict
        """
        if last.startswith(TOOL_RESULT_PREFIX):
            result = last[len(TOOL_RESULT_PREFIX):]
            return {"answer": "Según el directorio: " + result}
        match = EMPLOYEE_ID_PATTERN.search(last)
        if match:
            employee_id = match.group(0).upper()
            return {"tool": "get_employee", "args": {"employee_id": employee_id}}
        lowered = last.casefold()
        for department in self._departments:
            if department.casefold() in lowered:
                return {
                    "tool": "search_by_department",
                    "args": {"department": department},
                }
        return {"answer": HELP_ANSWER}


def build_models(
    settings: Settings,
    directory: EmployeeDirectory,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, LanguageModel]:
    """Crea un modelo por nombre configurado (``MODEL_SMALL`` y ``MODEL_LARGE``).

    Con ``fake`` son dos simulados con esos nombres; con ``gateway`` son dos
    modelos reales que comparten un cliente HTTP.

    :param settings: Configuración del producto
    :type settings: Settings
    :param directory: Directorio de empleados (para conocer los departamentos)
    :type directory: EmployeeDirectory
    :param sleep: Espera para los reintentos del gateway (inyectable en pruebas)
    :type sleep: Callable[[float], None]
    :return: Los modelos por nombre
    :rtype: dict[str, LanguageModel]
    :raises ValueError: Si el proveedor no está soportado
    """
    names = (settings.model_small, settings.model_large)
    if settings.model_provider == FAKE_PROVIDER:
        departments = directory.departments()
        return {name: FakeModel(departments, name=name) for name in names}
    if settings.model_provider == GATEWAY_PROVIDER:
        client = create_http_client()
        return {
            name: GatewayModel(name, settings, client, sleep=sleep) for name in names
        }
    raise ValueError(f"MODEL_PROVIDER {settings.model_provider!r} is not supported")
