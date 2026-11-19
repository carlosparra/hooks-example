"""La parte de QA.md que un programa puede revisar en el producto.

- pylint sobre ``app`` y ``tests``, con líneas de máximo 88 caracteres.
- Ningún emoji en el código ni en los documentos.
- En la raíz del producto, el único Markdown es ``README.md``; el resto va en ``doc/``.

Lo que un programa no ve (nombres claros, funciones pequeñas, valores fijos en el
código) lo revisa el agente ``qa-style``.
"""

import subprocess
import sys
from pathlib import Path

PRODUCT = Path(__file__).resolve().parent.parent / "product"
PYLINT = [
    sys.executable, "-m", "pylint", "app", "tests", "--max-line-length=88",
    "--fail-under=10",
    "--disable=missing-function-docstring,redefined-outer-name,too-few-public-methods",
]


def has_emoji(text: str) -> bool:
    """Indica si el texto tiene emojis o símbolos gráficos."""
    return any(ord(c) > 0xFFFF or 0x2600 <= ord(c) <= 0x27BF for c in text)


def problems(product: Path) -> list[str]:
    """Lista lo que incumple QA.md, sin contar pylint.

    :param product: Carpeta del producto
    :type product: pathlib.Path
    :return: Un texto por problema; vacía si todo está bien
    :rtype: list[str]
    """
    found = []
    paths = sorted(product.rglob("*"), key=lambda p: p.relative_to(product).as_posix())
    for path in paths:
        relative = path.relative_to(product).as_posix()
        is_text = path.suffix in {".py", ".md", ".html"}
        if is_text and has_emoji(path.read_text("utf-8")):
            found.append(f"emoji en {relative}")
        if path.suffix == ".md" and "/" not in relative and relative != "README.md":
            found.append(f"{relative} debe ir en doc/")
    if not (product / "README.md").exists():
        found.append("falta README.md")
    return found


def main() -> int:
    """Corre pylint y las revisiones de archivos; 0 si todo pasa."""
    lint = subprocess.run(PYLINT, cwd=PRODUCT, check=False).returncode
    found = problems(PRODUCT)
    for problem in found:
        print(f"  {problem}")
    ok = lint == 0 and not found
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
