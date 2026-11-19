"""Dibuja el pipeline de la última corrida a partir de la bitácora de la fábrica.

Lee ``output/activity.jsonl`` (lo escribe ``hooks/activity_log.py``), se queda con
los pasos del orquestador (cada agente y cada verificación) y escribe
``output/pipeline.md``: un diagrama Mermaid, que GitHub y los editores dibujan,
y una tabla con lo que tardó cada paso. Los agentes lanzados juntos quedan en la
misma columna: corrieron en paralelo.

Uso: ``uv run python scripts/pipeline.py``
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "output" / "activity.jsonl"
PIPELINE = ROOT / "output" / "pipeline.md"
# Agentes lanzados con menos de estos segundos de diferencia corrieron en paralelo
PARALLEL_GAP = 10


def step_name(event: dict) -> str | None:
    """Nombre del paso: el agente lanzado o la verificación corrida."""
    target = str(event.get("target") or "")
    if event["tool"] == "Agent":
        return target
    found = re.search(r"verification (\w+)", target)
    return f"verify {found.group(1)}" if event["tool"] == "Bash" and found else None


def last_activity(events: list[dict], agent: str, since: datetime) -> datetime:
    """Hora de la última herramienta de ``agent`` desde ``since``.

    Sirve para los agentes en paralelo: su lanzamiento regresa de inmediato,
    pero siguen trabajando. Se cuenta hasta que el orquestador lo vuelve a lanzar.
    """
    relaunches = [
        e["time"] for e in events
        if e["agent"] == "orchestrator"
        and e.get("target") == agent
        and e["time"] > since
    ]
    until = min(relaunches, default=datetime.max.replace(tzinfo=since.tzinfo))
    times = [
        e["time"] for e in events if e["agent"] == agent and since <= e["time"] < until
    ]
    return max(times, default=since)


def steps(lines: list[str]) -> list[dict]:
    """Pasos del orquestador con su duración en segundos.

    Un agente se mide desde la acción anterior del orquestador hasta su última
    herramienta. Una verificación, desde lo último que pasó hasta que termina.

    :param lines: Líneas JSON de la bitácora
    :type lines: list[str]
    :return: Pasos con ``name``, ``ok``, ``launch``, ``is_agent`` y ``seconds``
    :rtype: list[dict]
    """
    events = [json.loads(line) for line in lines if line.strip()]
    for event in events:
        event["time"] = datetime.fromisoformat(event["ts"])
    found, previous_any, previous_orchestrator = [], None, None
    for event in events:
        moment = event["time"]
        before_any, previous_any = previous_any or moment, moment
        if event["agent"] != "orchestrator":
            continue
        before, previous_orchestrator = previous_orchestrator or moment, moment
        name = step_name(event)
        if not name:
            continue
        is_agent = event["tool"] == "Agent"
        start = before if is_agent else before_any
        end = last_activity(events, name, moment) if is_agent else moment
        seconds = int((end - start).total_seconds())
        found.append({"name": name, "ok": event["ok"], "launch": moment,
                      "is_agent": is_agent, "seconds": seconds})
    return found


def columns(found: list[dict]) -> list[list[int]]:
    """Agrupa en columnas los pasos; los agentes lanzados juntos comparten columna.

    :return: Listas de índices de ``found``, en orden
    :rtype: list[list[int]]
    """
    grouped: list[list[int]] = []
    for index, step in enumerate(found):
        head: dict = found[grouped[-1][0]] if grouped else {}
        together = head.get("is_agent") and step["is_agent"] and (
            (step["launch"] - head["launch"]).total_seconds() <= PARALLEL_GAP
        )
        if together:
            grouped[-1].append(index)
        else:
            grouped.append([index])
    return grouped


def render(found: list[dict]) -> str:
    """Convierte los pasos en Markdown con un diagrama Mermaid y una tabla.

    :param found: Pasos de :func:`steps`
    :type found: list[dict]
    :return: El contenido de ``output/pipeline.md``
    :rtype: str
    """
    nodes = [
        f'    s{n}["{s["name"]}<br/>{s["seconds"]} s"]:::{"ok" if s["ok"] else "fail"}'
        for n, s in enumerate(found)
    ]
    grouped = columns(found)
    arrows = [
        f"    s{a} --> s{b}"
        for before, after in zip(grouped, grouped[1:])
        for a in before
        for b in after
    ]
    rows = [
        f"| {n + 1} | {s['name']} | {'pasó' if s['ok'] else 'falló'} | {s['seconds']} |"
        for n, s in enumerate(found)
    ]
    return "\n".join(
        ["# Pipeline de la fábrica", "", "```mermaid", "flowchart LR", *nodes, *arrows,
         "    classDef ok fill:#d4f4dd,stroke:#1e7b3a",
         "    classDef fail fill:#fde2e2,stroke:#a12a2a", "```", "",
         "| # | Paso | Resultado | Segundos |", "| --- | --- | --- | --- |", *rows, ""]
    )


def main() -> int:
    """Escribe ``output/pipeline.md`` y dice cuántos pasos encontró."""
    if not LOG.exists():
        print("[FAIL] no existe output/activity.jsonl: corre primero /factory")
        return 1
    found = steps(LOG.read_text(encoding="utf-8").splitlines())
    PIPELINE.write_text(render(found), encoding="utf-8")
    print(f"[OK] {len(found)} pasos en {PIPELINE.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
