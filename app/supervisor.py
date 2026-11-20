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
    """

    specialist: str
    method: str


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
        self._departments = [_fold(name) for name in directory.departments()]
        self._names = self._name_terms(directory)

    @staticmethod
    def _name_terms(directory: EmployeeDirectory) -> list[str]:
        """Junta nombres completos y sus partes para reconocer personas.

        :param directory: Directorio de empleados
        :type directory: EmployeeDirectory
        :return: Términos normalizados
        :rtype: list[str]
        """
        terms: list[str] = []
        for department in directory.departments():
            for person in directory.search_by_department(department):
                full = _fold(person.get("name", ""))
                terms.append(full)
                terms.extend(
                    part for part in full.split() if len(part) >= MIN_NAME_PART_CHARS
                )
        return terms

    def decide(self, question: str) -> Decision:
        """Elige el especialista; el orden de las reglas es fijo.

        :param question: Pregunta ya enmascarada
        :type question: str
        :return: La decisión
        :rtype: Decision
        """
        folded = _fold(question)
        if EMPLOYEE_ID.search(question):
            return Decision(EMPLOYEE, METHOD_RULES)
        if any(_mentions(folded, name) for name in self._departments):
            return Decision(DEPARTMENT, METHOD_RULES)
        if any(_mentions(folded, term) for term in self._names):
            return Decision(EMPLOYEE, METHOD_RULES)
        messages = [
            {"role": "system", "content": SUPERVISOR_PROMPT},
            {"role": "user", "content": question},
        ]
        completion = self._model.complete(messages)
        choice = completion.text.strip().strip("\"'.").casefold()
        specialist = DEPARTMENT if choice == DEPARTMENT else EMPLOYEE
        return Decision(specialist, METHOD_MODEL)
