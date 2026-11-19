"""Pruebas del hook de permisos: cada agente escribe solo en sus carpetas."""

import json
import subprocess
import sys

import pytest

from hooks import permissions
from hooks.permissions import ROOT, check


def write(agent, path, tool="Write"):
    return {"agent_type": agent, "tool_name": tool, "tool_input": {"file_path": path}}


@pytest.mark.parametrize(
    "agent, path",
    [
        ("architect", "output/plan.md"),
        ("deploy", "product/.github/workflows/ci.yml"),
        ("security", "product/doc/compliance-checklist.md"),
        ("architect", "product/doc/adr/0001-stateless-api.md"),
        ("qa-unit", "product/tests/test_agent.py"),
        ("developer", "product/app/main.py"),
        ("developer", "product/requirements.txt"),
    ],
)
def test_agent_can_write_in_its_folders(agent, path):
    assert check(write(agent, path)) is None


def test_developer_cannot_write_tests():
    reason = check(write("developer", "product/tests/test_agent.py"))
    assert "developer no puede escribir product/tests/test_agent.py" in reason


def test_qa_unit_cannot_write_code():
    assert check(write("qa-unit", "product/app/main.py", tool="Edit")) is not None


def test_absolute_paths_are_checked_too():
    assert check(write("developer", str(ROOT / "product/app/main.py"))) is None
    assert check(write("developer", str(ROOT / "hooks/permissions.py"))) is not None


def test_paths_outside_the_project_are_blocked():
    assert "no puede escribir" in check(write("developer", "product/app/../../../x"))


def test_reading_and_the_orchestrator_are_not_restricted():
    assert check({"agent_type": "developer", "tool_name": "Read"}) is None
    assert check(write(None, "product/app/main.py")) is None


@pytest.mark.parametrize("agent, code", [("developer", 0), ("qa-unit", 2)])
def test_hook_exit_code_tells_claude_code_what_to_do(agent, code):
    event = json.dumps(write(agent, "product/app/main.py"))
    hook = subprocess.run(
        [sys.executable, str(ROOT / "hooks/permissions.py")],
        input=event,
        capture_output=True,
        text=True,
        check=False,
    )
    assert hook.returncode == code


def test_architect_cannot_approve_its_own_publication():
    assert check(write("architect", "output/approved.txt")) is not None


@pytest.mark.parametrize(
    "tool, tool_input",
    [
        ("Read", {"file_path": "product/.env"}),
        ("Bash", {"command": "uv run --env-file .env uvicorn app.main:app"}),
        ("Grep", {"pattern": "TOKEN", "path": ".env"}),
        ("PowerShell", {"command": "Get-Content product/.env"}),
    ],
)
def test_nobody_reads_env_files(tool, tool_input):
    event = {"tool_name": tool, "tool_input": tool_input}
    assert check(event) == "Nadie lee .env: ahí van los secretos."


def test_env_example_and_writing_dockerignore_are_fine():
    example = {"tool_name": "Read", "tool_input": {"file_path": ".env.example"}}
    assert check(example) is None
    dockerignore = write("deploy", "product/.dockerignore")
    dockerignore["tool_input"]["content"] = ".env\n"
    assert check(dockerignore) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize(
    "command",
    ["uv run python scripts/publish.py hr-assistant", "git push", "gh repo create x"],
)
def test_publishing_needs_human_approval(tool, command, tmp_path, monkeypatch):
    monkeypatch.setattr(permissions, "ROOT", tmp_path)
    event = {"tool_name": tool, "tool_input": {"command": command}}
    assert check(event).startswith("Publicar requiere")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "approved.txt").write_text("ok", encoding="utf-8")
    assert check(event) is None
