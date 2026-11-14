"""Pruebas unitarias del directorio de empleados."""


def test_unknown_employee_is_reported_as_none(directory):
    assert directory.get_employee("EMP-9999") is None
    assert directory.get_employee("EMP-0004")["name"] == "Jorge Díaz"


def test_department_search_ignores_letter_case(directory):
    people = directory.search_by_department("tecnología")
    names = [employee["name"] for employee in people]
    assert names == ["Ana López", "Marta Ruiz", "Jorge Díaz"]
    assert directory.search_by_department("Legal") == []
