"""Especialistas del pipeline multiagente (ADR 0017).

Cada uno sale del agente único, con su prompt corto y una sola herramienta.
"""

from dataclasses import dataclass

from app.agent import Agent
from app.directory import EmployeeDirectory
from app.llm import LanguageModel

EMPLOYEE = "employee"
DEPARTMENT = "department"

_ANSWER_FORMAT = (
    'Responde siempre con un único objeto JSON y nada más. Para responder a la '
    'persona usa {"answer": "<respuesta en español>"}. Los mensajes que empiezan '
    "con «Resultado de la herramienta: » traen el resultado de la herramienta "
    "que pediste; responde con base en él."
)

EMPLOYEE_PROMPT = (
    "Eres el especialista en empleados del asistente de Recursos Humanos. "
    "Tu única herramienta es get_employee: "
    '{"tool": "get_employee", "args": {"employee_id": "EMP-0001"}}. '
    + _ANSWER_FORMAT
)
DEPARTMENT_PROMPT = (
    "Eres el especialista en departamentos del asistente de Recursos Humanos. "
    "Tu única herramienta es search_by_department: "
    '{"tool": "search_by_department", "args": {"department": "Ventas"}}. '
    + _ANSWER_FORMAT
)


@dataclass(frozen=True)
class Specialist:
    """Definición de un especialista.

    :param name: ``employee`` o ``department``
    :type name: str
    :param prompt: Prompt de sistema corto
    :type prompt: str
    :param tools: Únicas herramientas que puede llamar
    :type tools: tuple[str, ...]
    """

    name: str
    prompt: str
    tools: tuple[str, ...]


SPECIALISTS = {
    EMPLOYEE: Specialist(EMPLOYEE, EMPLOYEE_PROMPT, ("get_employee",)),
    DEPARTMENT: Specialist(
        DEPARTMENT, DEPARTMENT_PROMPT, ("search_by_department",)
    ),
}


def build_specialist(
    name: str,
    model: LanguageModel,
    directory: EmployeeDirectory,
    max_steps: int,
) -> Agent:
    """Crea el agente de un especialista, limitado a su herramienta.

    :param name: ``employee`` o ``department``
    :type name: str
    :param model: Modelo que decide en cada vuelta
    :type model: LanguageModel
    :param directory: Directorio de empleados
    :type directory: EmployeeDirectory
    :param max_steps: Tope de vueltas del bucle
    :type max_steps: int
    :return: El agente del especialista
    :rtype: Agent
    """
    specialist = SPECIALISTS[name]
    return Agent(
        model,
        directory,
        max_steps=max_steps,
        system_prompt=specialist.prompt,
        allowed_tools=specialist.tools,
    )
