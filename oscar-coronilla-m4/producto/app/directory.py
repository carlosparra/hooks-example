"""Directorio de empleados de solo lectura sobre un archivo JSON."""

import json
import unicodedata
from pathlib import Path
from typing import Any, Iterable


def normalize_text(text: str) -> str:
    """Pasa un texto a minúsculas y le quita los acentos.

    :param text: Texto original
    :type text: str
    :return: Texto normalizado para comparar
    :rtype: str
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class EmployeeDirectory:
    """Directorio inmutable de empleados.

    :param employees: Registros de empleados
    :type employees: Iterable[dict[str, Any]]
    """

    def __init__(self, employees: Iterable[dict[str, Any]]) -> None:
        self._employees = tuple(dict(employee) for employee in employees)

    @classmethod
    def from_file(cls, path: str | Path) -> "EmployeeDirectory":
        """Lee el directorio desde un archivo JSON.

        :param path: Ruta del archivo de empleados
        :type path: str | pathlib.Path
        :return: Directorio con los empleados del archivo
        :rtype: EmployeeDirectory
        :raises FileNotFoundError: Si el archivo no existe
        :raises ValueError: Si el contenido no es una lista JSON
        """
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Employees file not found: {file_path}")
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Employees file must contain a JSON list: {file_path}")
        return cls(data)

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        """Busca un empleado por su id.

        :param employee_id: Id del empleado, por ejemplo ``EMP-0004``
        :type employee_id: str
        :return: Copia del empleado o ``None`` si no existe
        :rtype: dict[str, Any] | None
        """
        wanted = str(employee_id).strip().upper()
        for employee in self._employees:
            if str(employee.get("id", "")).upper() == wanted:
                return dict(employee)
        return None

    def search_by_department(self, department: str) -> list[dict[str, Any]]:
        """Lista los empleados de un departamento.

        La comparación no distingue mayúsculas ni acentos.

        :param department: Nombre del departamento
        :type department: str
        :return: Copias de los empleados del departamento, en orden del archivo
        :rtype: list[dict[str, Any]]
        """
        wanted = normalize_text(str(department).strip())
        return [
            dict(employee)
            for employee in self._employees
            if normalize_text(str(employee.get("department", ""))) == wanted
        ]

    def departments(self) -> list[str]:
        """Devuelve los departamentos existentes, sin repetir y en orden de aparición.

        :return: Nombres de departamento
        :rtype: list[str]
        """
        names: list[str] = []
        for employee in self._employees:
            name = employee.get("department")
            if name and name not in names:
                names.append(name)
        return names
