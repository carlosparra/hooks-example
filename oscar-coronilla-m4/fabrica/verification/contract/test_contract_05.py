"""Contrato del reto: la PII nunca entra al modelo ni sale en una respuesta."""

import os
import subprocess
import sys

from verification.server import PRODUCT


def ask(api, question):
    return api.post("/ask", json={"question": question})


def test_a_question_with_an_email_is_rejected_without_echoing_it(api):
    response = ask(api, "¿Quién tiene el correo ana.lopez@empresa.com?")
    assert response.status_code == 422
    assert "sensitive data detected" in response.json()["detail"]
    assert "ana.lopez@empresa.com" not in response.text


def test_a_question_with_a_phone_is_rejected(api):
    assert ask(api, "Llama al 442 123 4567 y dime quién es").status_code == 422


def test_a_clean_question_still_works_and_reports_no_masking(api):
    body = ask(api, "¿Quién es EMP-0004?").json()
    assert "Jorge Díaz" in body["answer"]
    assert body["pii_masked"] == []


def test_metrics_count_blocked_questions(api):
    ask(api, "Mi correo es prueba@empresa.com")
    assert api.get("/metrics").json()["pii_blocked"] >= 1


def start(**env):
    settings = {
        **os.environ, "ENVIRONMENT": "production", "MODEL_PROVIDER": "gateway",
        "CF_ACCOUNT_ID": "0" * 32, "CF_API_TOKEN": "example", "CF_GATEWAY_ID": "default",
        "API_KEYS": "portal:" + "k" * 20, **env,
    }
    return subprocess.run([sys.executable, "-c", "import app.main"], cwd=PRODUCT,
                          env=settings, capture_output=True, text=True, timeout=30,
                          check=False)


def test_production_refuses_to_start_without_pii_detection():
    assert start(PII_DETECTION="true").returncode == 0
    assert start(PII_DETECTION="false").returncode != 0
