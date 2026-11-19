"""Pruebas del hook de bitácora y del dibujo del pipeline."""

import json
from datetime import datetime, timezone

from scripts import pipeline
from hooks.activity_log import ROOT, entry

NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)


def test_subagent_tools_are_logged_with_their_agent():
    event = {"agent_type": "qa-unit", "tool_name": "Write",
             "tool_input": {"file_path": "product/tests/test_x.py"},
             "hook_event_name": "PostToolUse"}
    assert entry(event, NOW) == {
        "ts": "2026-11-04T18:00:00+00:00", "agent": "qa-unit", "tool": "Write",
        "target": "product/tests/test_x.py", "ok": True,
    }


def test_paths_inside_the_project_are_logged_relative():
    event = {"agent_type": "developer", "tool_name": "Write",
             "tool_input": {"file_path": f"{ROOT}/product/app/main.py"}}
    assert entry(event, NOW)["target"] == "product/app/main.py"


def test_orchestrator_steps_and_failures_are_logged():
    event = {"tool_name": "Bash", "hook_event_name": "PostToolUseFailure",
             "tool_input": {"command": "uv run python -m verification unit"}}
    line = entry(event, NOW)
    assert line["agent"] == "orchestrator"
    assert line["ok"] is False


def log_line(minute, agent, tool, target, ok=True):
    ts = f"2026-11-04T18:{minute:02d}:00+00:00"
    line = {"ts": ts, "agent": agent, "tool": tool, "target": target, "ok": ok}
    return json.dumps(line)


LINES = [
    log_line(0, "orchestrator", "Read", "spec/01-architecture.md"),
    log_line(1, "architect", "Write", "output/plan.md"),
    log_line(2, "orchestrator", "Agent", "architect"),
    log_line(5, "orchestrator", "Bash", "uv run python -m verification unit", ok=False),
    log_line(9, "orchestrator", "Read", "output/plan.md"),
]


def summary(found):
    return [(s["name"], s["ok"], s["seconds"]) for s in found]


def test_pipeline_keeps_only_agents_and_verifications():
    assert summary(pipeline.steps(LINES)) == [
        ("architect", True, 120),
        ("verify unit", False, 180),
    ]


PARALLEL = [
    log_line(0, "orchestrator", "Read", "output/plan.md"),
    log_line(1, "orchestrator", "Agent", "costs"),
    log_line(1, "orchestrator", "Agent", "qa-e2e"),
    log_line(3, "qa-e2e", "Write", "product/e2e/test_page.py"),
    log_line(6, "costs", "Edit", "product/app/main.py"),
    log_line(7, "orchestrator", "Bash", "uv run python -m verification unit"),
]


def test_parallel_agents_are_measured_by_their_own_work():
    assert summary(pipeline.steps(PARALLEL)) == [
        ("costs", True, 360),
        ("qa-e2e", True, 120),
        ("verify unit", True, 60),
    ]


def test_parallel_agents_share_a_column_in_the_diagram():
    text = pipeline.render(pipeline.steps(PARALLEL))
    for arrow in ("s0 --> s2", "s1 --> s2"):
        assert arrow in text


def test_pipeline_is_a_mermaid_diagram_with_a_table():
    text = pipeline.render(pipeline.steps(LINES))
    assert "flowchart LR" in text
    assert "s0 --> s1" in text
    assert ":::fail" in text
    assert "| 2 | verify unit | falló | 180 |" in text


def test_pipeline_needs_the_log(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "LOG", tmp_path / "activity.jsonl")
    assert pipeline.main() == 1
    assert "corre primero /factory" in capsys.readouterr().out


def test_pipeline_writes_the_markdown(tmp_path, monkeypatch):
    log = tmp_path / "activity.jsonl"
    log.write_text("\n".join(LINES), encoding="utf-8")
    monkeypatch.setattr(pipeline, "LOG", log)
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "PIPELINE", tmp_path / "pipeline.md")
    assert pipeline.main() == 0
    assert "verify unit" in (tmp_path / "pipeline.md").read_text(encoding="utf-8")
