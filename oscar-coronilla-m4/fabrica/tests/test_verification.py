"""Pruebas del corredor de verificaciones, sin correr el producto."""

import subprocess

import verification.__main__ as runner


def test_unknown_step_shows_usage(capsys):
    assert runner.run("deploy") == 2
    assert "Uso:" in capsys.readouterr().out


def test_missing_product_fails_with_a_clear_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "PRODUCT", tmp_path / "product")
    assert runner.run("unit") == 1
    assert "todavía no existe product/app/" in capsys.readouterr().out


def test_step_returns_the_exit_code_of_pytest(tmp_path, monkeypatch, capsys):
    (tmp_path / "product" / "app").mkdir(parents=True)
    monkeypatch.setattr(runner, "PRODUCT", tmp_path / "product")
    calls = []

    def fake_run(command, cwd, check):
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.run("contract") == 1
    assert "verification/contract" in calls[0][0]
    assert "[FAIL] contract" in capsys.readouterr().out
