"""Publica el producto: crea su repositorio privado en GitHub y hace el push.

Uso: ``uv run python scripts/publish.py <nombre-del-repositorio>``

Solo corre si una persona aprobó (existe ``output/approved.txt``); además, el hook
``hooks/permissions.py`` bloquea este comando sin esa aprobación. Render toma el
código de ese repositorio y publica cuando el pipeline de CI pasa.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT = ROOT / "product"
APPROVAL = ROOT / "output" / "approved.txt"
MESSAGE = "HR assistant built by the agent factory"


def problems() -> list[str]:
    """Lo que impide publicar; vacía si se puede.

    :return: Un texto por problema
    :rtype: list[str]
    """
    found = []
    if not APPROVAL.exists():
        found.append("falta la aprobación de una persona (output/approved.txt)")
    ignore = PRODUCT / ".gitignore"
    if not ignore.exists() or ".env" not in ignore.read_text(encoding="utf-8"):
        found.append("product/.gitignore debe excluir .env")
    if not (PRODUCT / "render.yaml").exists():
        found.append("falta product/render.yaml")
    return found


def commands(repo: str, first_time: bool) -> list[list[str]]:
    """Los comandos de git y gh, en orden.

    :param repo: Nombre del repositorio en GitHub
    :type repo: str
    :param first_time: ``True`` si el producto todavía no es un repositorio
    :type first_time: bool
    :return: Cada comando como lista de argumentos
    :rtype: list[list[str]]
    """
    commit = [["git", "add", "-A"], ["git", "commit", "-m", MESSAGE]]
    if first_time:
        return [["git", "init", "-b", "main"], *commit,
                ["gh", "repo", "create", repo, "--private", "--source", ".", "--push"]]
    return [*commit, ["git", "push"]]


def main(args: list[str]) -> int:
    """Revisa que se pueda publicar y corre los comandos; 0 si todo sale bien."""
    if len(args) != 1:
        print("Uso: python scripts/publish.py <nombre-del-repositorio>")
        return 2
    found = problems()
    for problem in found:
        print(f"  {problem}")
    if found:
        print("[FAIL] publish")
        return 1
    for command in commands(args[0], not (PRODUCT / ".git").exists()):
        print("$", " ".join(command))
        if subprocess.run(command, cwd=PRODUCT, check=False).returncode != 0:
            print("[FAIL] publish")
            return 1
    print("[OK] publish")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
