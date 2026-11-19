"""Hook PostToolUse: la fábrica también se observa.

Después de cada herramienta, de cualquier agente, agrega una línea JSON a
``output/activity.jsonl``: cuándo, quién, qué herramienta y si salió bien. Con
esa bitácora ``scripts/pipeline.py`` dibuja el pipeline de la corrida.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "output" / "activity.jsonl"


def entry(event: dict, now: datetime) -> dict:
    """Arma la línea de la bitácora a partir del evento de Claude Code."""
    tool_input = event.get("tool_input", {})
    target = (tool_input.get("subagent_type") or tool_input.get("command")
              or tool_input.get("file_path"))
    return {
        "ts": now.isoformat(timespec="seconds"),
        "agent": event.get("agent_type") or "orchestrator",
        "tool": event.get("tool_name"),
        # Rutas relativas al proyecto: la bitácora no expone carpetas personales
        "target": target.replace(f"{ROOT}{os.sep}", "").replace(f"{ROOT}/", "")
        if target else None,
        "ok": event.get("hook_event_name") != "PostToolUseFailure",
    }


if __name__ == "__main__":
    LOG.parent.mkdir(exist_ok=True)
    line = entry(json.load(sys.stdin), datetime.now(timezone.utc))
    with LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(line, ensure_ascii=False) + "\n")
