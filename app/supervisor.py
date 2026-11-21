"""Supervisor del pipeline: elige el especialista con reglas (ADR 0017).

Solo si ninguna regla aplica le pregunta al modelo pequeño.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.directory import EmployeeDirectory
from app.llm import LanguageModel
from app.specialists import DEPARTMENT, EMPLOYEE

METHOD_RULES = "rules"
METHOD_MODEL = "model"
EMPLOYEE_ID = re.compile(r"\bEMP-\d{4}\b", re.IGNORECASE)
MIN_NAME_PART_CHARS = 3
SUPERVISOR_PROMPT = (
    "Elige el especialista para la pregunta. Responde solo con una palabra: "
    "employee (una persona) o department (un departamento)."
)


@dataclass(frozen=True)
class Decision:
    """Especialista elegido y cómo se eligió.

    :param specialist: ``employee`` o ``department``
    :type specialist: str
    :param method: ``rules`` o ``model``
    :type method: str
    :param tool: Herramienta que el código llama antes del modelo (solo con
        reglas); ``None`` si no hay
    :type tool: str | None
    :param tool_args: Argumentos de esa herramienta
    :type tool_args: dict | None
    """

    specialist: str
    method: str
    tool: str | None = None
    tool_args: dict | None = None


def _fold(text: str) -> str:
    """Pasa a minúsculas y quita acentos.

    :param text: Texto original
    :type text: str
    :return: Texto sin mayúsculas ni acentos
    :rtype: str
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _mentions(folded_question: str, folded_term: str) -> bool:
    """Dice si el término aparece como palabra completa.

    :param folded_question: Pregunta ya normalizada
    :type folded_question: str
    :param folded_term: Término ya normalizado
    :type folded_term: str
    :return: ``True`` si aparece
    :rtype: bool
    """
    pattern = r"(?<!\w)" + re.escape(folded_term) + r"(?!\w)"
    return re.search(pattern, folded_question) is not None


class Supervisor:
    """Elige entre el especialista de empleado y el de departamento.

    :param directory: Directorio (departamentos y nombres conocidos)
    :type directory: EmployeeDirectory
    :param model: Modelo pequeño para las preguntas poco claras
    :type model: LanguageModel
    """

    def __init__(self, directory: EmployeeDirectory, model: LanguageModel):
        self._model = model
        self._departments = {
            _fold(name): name for name in directory.departments()
        }
        self._names = self._name_terms(directory)

    @staticmethod
    def _name_terms(directory: EmployeeDirectory) -> dict[str, set[str]]:
        """Junta nombres completos y sus partes, con los ids que les corresponden.

        :param directory: Directorio de empleados
        :type directory: EmployeeDirectory
        :return: Término normalizado y ids de las personas que lo llevan
        :rtype: dict[str, set[str]]
        """
        terms: dict[str, set[str]] = {}
        for department in directory.departments():
            for person in directory.search_by_department(department):
                full = _fold(person.get("name", ""))
                person_id = person.get("id", "")
                parts = [
                    part for part in full.split() if len(part) >= MIN_NAME_PART_CHARS
                ]
                for term in [full, *parts]:
                    terms.setdefault(term, set()).add(person_id)
        return terms

    def decide(self, question: str) -> Decision:
        """Elige el especialista; el orden de las reglas es fijo.

        :param question: Pregunta ya enmascarada
        :type question: str
        :return: La decisión
        :rtype: Decision
        """
        folded = _fold(question)
        found = EMPLOYEE_ID.search(question)
        if found:
            return Decision(
                EMPLOYEE,
                METHOD_RULES,
                "get_employee",
                {"employee_id": found.group(0).upper()},
            )
        for folded_name, name in self._departments.items():
            if _mentions(folded, folded_name):
                return Decision(
                    DEPARTMENT,
                    METHOD_RULES,
                    "search_by_department",
                    {"department": name},
                )
        person_ids: set[str] = set()
        for term, ids in self._names.items():
            if _mentions(folded, term):
                person_ids |= ids
        # Solo una persona posible: se conoce el id. Si es ambiguo no se adivina.
        if len(person_ids) == 1:
            return Decision(
                EMPLOYEE,
                METHOD_RULES,
                "get_employee",
                {"employee_id": next(iter(person_ids))},
            )
        messages = [
            {"role": "system", "content": SUPERVISOR_PROMPT},
            {"role": "user", "content": question},
        ]
        completion = self._model.complete(messages)
        choice = completion.text.strip().strip("\"'.").casefold()
        specialist = DEPARTMENT if choice == DEPARTMENT else EMPLOYEE
        return Decision(specialist, METHOD_MODEL)
