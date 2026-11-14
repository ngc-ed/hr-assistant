"""Directorio de empleados de solo lectura."""

import json
from pathlib import Path


class EmployeeDirectory:
    """Directorio de empleados en memoria, de solo lectura.

    :param employees: Lista de empleados (diccionarios con ``id``, ``name``, etc.)
    :type employees: list[dict]
    """

    def __init__(self, employees: list[dict]):
        self._employees = tuple(dict(employee) for employee in employees)

    @classmethod
    def from_file(cls, path: str | Path) -> "EmployeeDirectory":
        """Carga el directorio desde un archivo JSON.

        :param path: Ruta del archivo de empleados
        :type path: str | Path
        :return: El directorio cargado
        :rtype: EmployeeDirectory
        """
        with open(path, encoding="utf-8") as handle:
            return cls(json.load(handle))

    def get_employee(self, employee_id: str) -> dict | None:
        """Busca un empleado por id.

        :param employee_id: Id del empleado, por ejemplo ``EMP-0004``
        :type employee_id: str
        :return: Copia del empleado o ``None`` si no existe
        :rtype: dict | None
        """
        wanted = employee_id.strip().upper()
        for employee in self._employees:
            if employee.get("id", "").upper() == wanted:
                return dict(employee)
        return None

    def search_by_department(self, department: str) -> list[dict]:
        """Lista los empleados de un departamento, sin distinguir mayúsculas.

        :param department: Nombre del departamento
        :type department: str
        :return: Copias de los empleados del departamento, en el orden de los datos
        :rtype: list[dict]
        """
        wanted = department.strip().casefold()
        return [
            dict(employee)
            for employee in self._employees
            if employee.get("department", "").casefold() == wanted
        ]

    def departments(self) -> list[str]:
        """Devuelve los departamentos existentes, sin repetir.

        :return: Nombres de departamento en el orden en que aparecen
        :rtype: list[str]
        """
        names: list[str] = []
        for employee in self._employees:
            name = employee.get("department")
            if name and name not in names:
                names.append(name)
        return names
