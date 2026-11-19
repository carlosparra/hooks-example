"""Arranca el producto con el modelo simulado para probarlo por HTTP.

Las verificaciones no importan el código del producto: le hablan como un
cliente, así que valen sin importar cómo lo haya escrito el agente.
"""

import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

PRODUCT = Path(__file__).resolve().parent.parent / "product"
# Clave de prueba de la fábrica: no es un secreto, solo existe en estas corridas
FACTORY_KEY = "factory-key-0123456789"
DEFAULTS = {
    "MODEL_PROVIDER": "fake",
    "API_KEYS": f"factory:{FACTORY_KEY}",
    "RATE_LIMIT_PER_MINUTE": "1000",
}


@contextmanager
def running_product(port: int, **env: str):
    """Corre ``uvicorn app.main:app`` en ``port`` mientras dure el bloque.

    El cliente que entrega ya manda la clave de la fábrica en ``X-API-Key``.
    """
    settings = {**os.environ, **DEFAULTS, **env}
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)]
    server = subprocess.Popen(command, cwd=PRODUCT, env=settings)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(40):
            try:
                httpx.get(f"{url}/health", timeout=1)
                break
            except httpx.TransportError:
                time.sleep(0.25)
        yield httpx.Client(
            base_url=url, timeout=10, headers={"X-API-Key": FACTORY_KEY}
        )
    finally:
        server.terminate()
        server.wait(timeout=10)
