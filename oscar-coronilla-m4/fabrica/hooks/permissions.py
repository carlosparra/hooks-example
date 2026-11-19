"""Hook PreToolUse: cada agente escribe solo en sus carpetas (mínima agencia).

Claude Code llama a este script antes de cada herramienta y le pasa por stdin un
JSON con ``agent_type`` (el agente), ``tool_name`` y ``tool_input``. Si el script
termina con código 2, la herramienta se bloquea y el agente lee el motivo.

Sesión 4: dos reglas para todos, también para el orquestador. Nadie lee ``.env``,
y nadie publica sin ``output/approved.txt``, que solo existe si una persona aprobó.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Dónde puede escribir cada agente. Quien escribe el código no escribe sus pruebas.
WRITABLE = {
    "architect": ["output/plan.md", "product/doc/"],
    "qa-unit": ["product/tests/"],
    "qa-e2e": ["product/e2e/"],
    "qa-style": ["output/qa-review.md"],
    "developer": ["product/app/", "product/data/", "product/requirements.txt"],
    "observability": ["product/app/", "product/requirements.txt", "product/README.md"],
    "costs": ["product/app/", "product/data/", "product/requirements.txt",
              "product/README.md", "product/.env.example"],
    "security": ["product/app/", "product/requirements.txt", "product/README.md",
                 "product/.env.example", "product/doc/compliance-checklist.md"],
    "deploy": ["product/Dockerfile", "product/.dockerignore", "product/render.yaml",
               "product/.github/", "product/scripts/", "product/.gitignore"],
    "triage": ["output/triage.md"],
}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
# En Windows, Claude Code usa PowerShell como terminal en lugar de Bash
SHELL_TOOLS = {"Bash", "PowerShell"}
SECRETS = re.compile(r"\.env(?![\w.])")  # .env sí; .env.example no
PUBLISH = re.compile(r"publish\.py|git push|gh repo create")


def check(event: dict) -> str | None:
    """Devuelve el motivo del bloqueo, o ``None`` si la herramienta puede correr."""
    agent, tool = event.get("agent_type"), event.get("tool_name")
    tool_input = event.get("tool_input", {})
    if tool not in WRITE_TOOLS and SECRETS.search(json.dumps(tool_input)):
        return "Nadie lee .env: ahí van los secretos."
    publishes = tool in SHELL_TOOLS and PUBLISH.search(tool_input.get("command", ""))
    if publishes and not (ROOT / "output" / "approved.txt").exists():
        return "Publicar requiere que una persona lo apruebe (output/approved.txt)."
    if agent not in WRITABLE or tool not in WRITE_TOOLS:
        return None
    target = (ROOT / tool_input.get("file_path", "")).resolve()
    path = target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else ""
    if any(path == ok or path.startswith(ok) for ok in WRITABLE[agent]):
        return None
    allowed = ", ".join(WRITABLE[agent])
    return f"{agent} no puede escribir {path or target}. Solo puede en: {allowed}"


if __name__ == "__main__":
    REASON = check(json.load(sys.stdin))
    if REASON:
        print(REASON, file=sys.stderr)
    sys.exit(2 if REASON else 0)
