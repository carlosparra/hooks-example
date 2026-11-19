"""Pruebas de ``app.directory``: busquedas de solo lectura sobre los empleados."""

import pytest

from app.directory import EmployeeDirectory


def test_employee_is_found_by_id_and_unknown_id_returns_nothing(directory):
    assert directory.get_employee("EMP-0004")["name"] == "Jorge Díaz"
    assert directory.get_employee("EMP-9999") is None


def test_department_search_ignores_case_and_accents(directory):
    employees = directory.search_by_department("TECNOLOGIA")
    names = [employee["name"] for employee in employees]

    assert names == ["Ana López", "Marta Ruiz", "Jorge Díaz"]
    assert directory.search_by_department("Marketing") == []


def test_missing_data_file_is_reported(tmp_path):
    missing = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="missing.json"):
        EmployeeDirectory.from_file(missing)
