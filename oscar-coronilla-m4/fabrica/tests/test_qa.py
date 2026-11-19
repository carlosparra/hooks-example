"""Pruebas de la revisión automática de QA.md sobre el producto."""

import subprocess

from verification import qa


def make_product(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_a_clean_product_has_no_problems(tmp_path):
    product = make_product(tmp_path, {"README.md": "# HR", "doc/adr/0001.md": "x"})
    assert not qa.problems(product)


def test_emojis_loose_markdown_and_missing_readme_are_reported(tmp_path):
    files = {"app/x.py": "# listo " + chr(0x2705), "NOTES.md": "x"}
    product = make_product(tmp_path, files)
    assert qa.problems(product) == [
        "NOTES.md debe ir en doc/", "emoji en app/x.py", "falta README.md",
    ]


def test_qa_fails_when_pylint_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(qa, "PRODUCT", make_product(tmp_path, {"README.md": "# HR"}))
    monkeypatch.setattr(
        qa.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1)
    )
    assert qa.main() == 1
