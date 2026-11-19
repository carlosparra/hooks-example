"""Lista de QA.md de la fábrica (no del producto), para Windows, Linux y macOS.

Corre las pruebas de los hooks y de la verificación con cobertura, pylint y busca
emojis. Termina con código 0 solo si todo pasa.

Uso: ``uv run python scripts/verify.py``
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ("hooks", "verification", "scripts", "tests")
CHECKS = {
    "Tests and coverage >= 80%": [
        "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
        "--cov=hooks", "--cov=verification", "--cov-fail-under=80",
        "--cov-config=scripts/coverage.ini",
    ],
    "Pylint": [
        "-m", "pylint", *CODE, "--max-line-length=88", "--fail-under=9.5",
        "--disable=missing-function-docstring,missing-module-docstring",
    ],
}
TEXT = ("*.py", "*.md", "*.json")


def has_emoji(text: str) -> bool:
    """Indica si el texto tiene emojis o símbolos gráficos.

    :param text: Texto a revisar
    :type text: str
    :return: ``True`` si hay al menos uno
    :rtype: bool
    """
    return any(ord(c) > 0xFFFF or 0x2600 <= ord(c) <= 0x27BF for c in text)


def files_with_emojis() -> list[str]:
    """Lista los archivos de la fábrica que tienen emojis.

    :return: Rutas relativas
    :rtype: list[str]
    """
    paths = [p for pattern in TEXT for p in ROOT.rglob(pattern)]
    skip = (".venv", "product", "output")
    return sorted(
        str(p.relative_to(ROOT))
        for p in paths
        if not any(part in skip for part in p.relative_to(ROOT).parts)
        and has_emoji(p.read_text(encoding="utf-8"))
    )


def main() -> int:
    """Corre cada verificación e imprime el resumen.

    :return: 0 si todo pasa, 1 si algo falla
    :rtype: int
    """
    results = {}
    for name, args in CHECKS.items():
        run = subprocess.run([sys.executable, *args], cwd=ROOT, check=False)
        results[name] = run.returncode == 0
    emojis = files_with_emojis()
    results["No emojis"] = not emojis
    print("\nQA checklist")
    for name, passed in results.items():
        print(f"  [{'OK' if passed else 'FAIL'}] {name}")
    for path in emojis:
        print(f"      emoji in {path}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
