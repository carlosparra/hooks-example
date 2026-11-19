"""Corre una verificación del producto y termina con su código de salida.

Uso: ``uv run python -m verification <paso>``, con uno de estos pasos:

- ``unit``: las pruebas que escribió qa-unit, con cobertura de 80 % o más.
- ``contract``: las pruebas de la fábrica contra el producto corriendo.
- ``qa``: la parte de QA.md que revisa un programa (``verification/qa.py``).
- ``e2e``: las pruebas de Playwright que escribió qa-e2e (``verification/e2e.py``).
- ``evaluate``: costo y calidad contra la línea base (``verification/evaluate.py``).
- ``production <url>``: la prueba de humo contra Render (``verification.production``).

Código 0: pasa. Cualquier otro: falla, y la salida dice por qué.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT = ROOT / "product"
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
STEPS = {
    "unit": (PYTEST + ["tests", "--cov=app", "--cov-fail-under=80"], PRODUCT),
    "contract": (PYTEST + ["verification/contract"], ROOT),
    "qa": ([sys.executable, "-m", "verification.qa"], ROOT),
    "e2e": ([sys.executable, "-m", "verification.e2e"], ROOT),
    "evaluate": ([sys.executable, "-m", "verification.evaluate"], ROOT),
    "production": ([sys.executable, "-m", "verification.production"], ROOT),
}


def run(step: str, extra: list[str] | None = None) -> int:
    """Corre la verificación ``step`` e imprime ``[OK]`` o ``[FAIL]``.

    ``extra`` son argumentos para el paso, por ejemplo la URL de ``production``.
    """
    if step not in STEPS:
        print(f"Uso: python -m verification {{{'|'.join(STEPS)}}}")
        return 2
    command, folder = STEPS[step]
    if not (PRODUCT / "app").is_dir():
        print(f"[FAIL] {step}: todavía no existe product/app/")
        return 1
    code = subprocess.run(command + (extra or []), cwd=folder, check=False).returncode
    print(f"[{'OK' if code == 0 else 'FAIL'}] {step}")
    return code


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "", sys.argv[2:]))
