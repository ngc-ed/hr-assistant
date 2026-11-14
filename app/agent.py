"""Agente único con bucle con tope y dos herramientas de solo lectura (ADR 0003)."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from app.directory import EmployeeDirectory
from app.llm import TOOL_RESULT_PREFIX, Completion, LanguageModel
from app.tracing import traceable

STEP_CAP_ANSWER = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)

ToolCallback = Callable[[str, dict], None]


@dataclass
class AgentResult:  # pylint: disable=too-many-instance-attributes
    """Resultado de una pregunta al agente.

    :param answer: Respuesta final en español
    :type answer: str
    :param steps: Vueltas del bucle que se usaron
    :type steps: int
    :param tools_used: Herramientas ejecutadas, en orden
    :type tools_used: list[str]
    :param input_tokens: Tokens de entrada sumados entre vueltas
    :type input_tokens: int
    :param output_tokens: Tokens de salida sumados entre vueltas
    :type output_tokens: int
    :param stopped: ``True`` si se llegó al tope de vueltas sin respuesta
    :type stopped: bool
    :param cached_calls: Llamadas servidas desde la caché del gateway
    :type cached_calls: int
    :param billable_input_tokens: Tokens de entrada de llamadas no cacheadas
    :type billable_input_tokens: int
    :param billable_output_tokens: Tokens de salida de llamadas no cacheadas
    :type billable_output_tokens: int
    """

    answer: str
    steps: int
    tools_used: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    stopped: bool = False
    cached_calls: int = 0
    billable_input_tokens: int = 0
    billable_output_tokens: int = 0

    def add_usage(self, completion: Completion) -> None:
        """Suma los tokens de una vuelta; las cacheadas no se facturan.

        :param completion: Respuesta del modelo en esta vuelta
        :type completion: Completion
        """
        self.input_tokens += completion.input_tokens
        self.output_tokens += completion.output_tokens
        if completion.cached:
            self.cached_calls += 1
            return
        self.billable_input_tokens += completion.input_tokens
        self.billable_output_tokens += completion.output_tokens


@dataclass(frozen=True)
class _Tool:
    """Herramienta registrada: función y nombre de su único argumento."""

    function: Callable[[str], str]
    argument: str


class Agent:
    """Agente que alterna entre el modelo y las herramientas hasta responder.

    :param model: Modelo que decide en cada vuelta
    :type model: LanguageModel
    :param directory: Directorio de empleados que usan las herramientas
    :type directory: EmployeeDirectory
    :param max_steps: Tope de vueltas del bucle
    :type max_steps: int
    """

    def __init__(
        self, model: LanguageModel, directory: EmployeeDirectory, max_steps: int
    ):
        self._model = model
        self._directory = directory
        self._max_steps = max_steps
        self._tools = {
            "get_employee": _Tool(self._get_employee, "employee_id"),
            "search_by_department": _Tool(self._search_by_department, "department"),
        }

    @traceable(run_type="chain", name="agent_run")
    def run(
        self,
        question: str,
        history: list[dict],
        on_tool_call: ToolCallback | None = None,
    ) -> AgentResult:
        """Responde una pregunta usando el historial que manda el cliente.

        :param question: Pregunta de la persona
        :type question: str
        :param history: Turnos anteriores con ``role`` y ``content``
        :type history: list[dict]
        :param on_tool_call: Se llama con nombre y argumentos de cada herramienta
            que sí se ejecuta (para auditoría); opcional
        :type on_tool_call: Callable[[str, dict], None] | None
        :return: La respuesta y sus métricas
        :rtype: AgentResult
        """
        messages = [
            {"role": item["role"], "content": item["content"]} for item in history
        ]
        messages.append({"role": "user", "content": question})
        result = AgentResult(
            answer=STEP_CAP_ANSWER, steps=self._max_steps, stopped=True
        )
        for step in range(1, self._max_steps + 1):
            completion = self._call_model(messages)
            result.add_usage(completion)
            reply = _parse_reply(completion.text)
            if reply is not None and isinstance(reply.get("answer"), str):
                result.answer = reply["answer"]
                result.steps = step
                result.stopped = False
                return result
            tool_output = self._execute(reply, result.tools_used, on_tool_call)
            messages.append({"role": "assistant", "content": completion.text})
            messages.append(
                {"role": "user", "content": TOOL_RESULT_PREFIX + tool_output}
            )
        return result

    @traceable(run_type="llm", name="model_call")
    def _call_model(self, messages: list[dict]) -> Completion:
        """Pide al modelo la siguiente respuesta (separado para trazarlo).

        :param messages: Conversación con ``role`` y ``content``
        :type messages: list[dict]
        :return: La respuesta del modelo
        :rtype: Completion
        """
        return self._model.complete(messages)

    @traceable(run_type="tool", name="tool_call")
    def _execute(
        self,
        reply: dict | None,
        tools_used: list[str],
        on_tool_call: ToolCallback | None = None,
    ) -> str:
        """Ejecuta la herramienta pedida o describe el error.

        :param reply: Respuesta del modelo ya parseada (``None`` si no era JSON)
        :type reply: dict | None
        :param tools_used: Lista donde se anota la herramienta ejecutada
        :type tools_used: list[str]
        :param on_tool_call: Aviso de la herramienta que sí se ejecuta; opcional
        :type on_tool_call: Callable[[str, dict], None] | None
        :return: Resultado de la herramienta o mensaje de error
        :rtype: str
        """
        if reply is None:
            return "Error: la respuesta del modelo no es un objeto JSON válido."
        name = reply.get("tool")
        tool = self._tools.get(name) if isinstance(name, str) else None
        if tool is None:
            return f"Error: herramienta desconocida {name!r}."
        args = reply.get("args")
        if (
            not isinstance(args, dict)
            or set(args) != {tool.argument}
            or not isinstance(args[tool.argument], str)
        ):
            return f"Error: argumentos inválidos para {name}."
        tools_used.append(name)
        if on_tool_call is not None:
            on_tool_call(name, dict(args))
        return tool.function(args[tool.argument])

    def _get_employee(self, employee_id: str) -> str:
        """Herramienta ``get_employee``.

        :param employee_id: Id del empleado
        :type employee_id: str
        :return: El empleado en JSON o un aviso si no existe
        :rtype: str
        """
        employee = self._directory.get_employee(employee_id)
        if employee is None:
            return f"No existe un empleado con id {employee_id}."
        return json.dumps(employee, ensure_ascii=False)

    def _search_by_department(self, department: str) -> str:
        """Herramienta ``search_by_department``.

        :param department: Nombre del departamento
        :type department: str
        :return: Los empleados en JSON o un aviso si no hay ninguno
        :rtype: str
        """
        people = self._directory.search_by_department(department)
        if not people:
            return f"No hay empleados en el departamento {department}."
        return json.dumps(people, ensure_ascii=False)


def _parse_reply(text: str) -> dict | None:
    """Parsea la respuesta del modelo como objeto JSON.

    :param text: Texto devuelto por el modelo
    :type text: str
    :return: El objeto o ``None`` si no es un objeto JSON
    :rtype: dict | None
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None
