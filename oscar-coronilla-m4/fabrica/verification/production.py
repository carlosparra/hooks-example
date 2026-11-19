"""Prueba de humo contra el producto publicado.

Uso: ``uv run python -m verification production https://<servicio>.onrender.com``

La clave se lee de la variable ``SMOKE_API_KEY``: nunca va en el comando ni en
el chat, porque quedaría en el historial.
"""

import os
import sys

import httpx


def smoke(url: str, key: str, client: httpx.Client) -> bool:
    """Comprueba ``/health``, ``/ask`` sin clave y ``/ask`` con clave.

    Imprime el código recibido en cada una: con él se ve la causa de una falla
    (401: la clave no coincide; 502: el modelo no responde).
    """
    question = {"question": "¿Quién es EMP-0004?"}
    checks = [
        ("GET /health", 200, client.get(f"{url}/health")),
        ("POST /ask sin clave", 401, client.post(f"{url}/ask", json=question)),
        ("POST /ask con clave", 200, client.post(
            f"{url}/ask", json=question, headers={"X-API-Key": key}
        )),
    ]
    for name, expected, response in checks:
        status = "OK" if response.status_code == expected else "FAIL"
        print(f"  [{status}] {name} -> {response.status_code} (esperado {expected})")
    return all(response.status_code == expected for _, expected, response in checks)


def main(args: list[str]) -> int:
    """Corre la prueba de humo; 0 si todo pasa."""
    key = os.environ.get("SMOKE_API_KEY", "")
    if len(args) != 1 or not key:
        print("Uso: SMOKE_API_KEY=<clave> python -m verification production <url>")
        return 2
    # Render despierta el servicio dormido en hasta un minuto
    with httpx.Client(timeout=90) as client:
        passed = smoke(args[0].rstrip("/"), key, client)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
