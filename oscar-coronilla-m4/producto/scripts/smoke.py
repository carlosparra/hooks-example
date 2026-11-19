"""Prueba de humo contra el HR Assistant publicado.

Uso: ``python scripts/smoke.py https://<servicio>.onrender.com``

La clave se lee de la variable ``SMOKE_API_KEY``, nunca de un argumento: un
argumento queda en el historial de la terminal. La clave nunca se imprime.
Comprueba tres cosas e imprime ``[OK]`` o ``[FAIL]`` en cada una:

- ``GET /health`` responde 200.
- ``POST /ask`` sin clave responde 401.
- ``POST /ask`` con clave responde 200.

Código de salida: 0 si todo pasa, 1 si algo falla, 2 si falta la URL o la clave.
"""

import os
import sys
from collections.abc import Callable

import httpx

QUESTION = {"question": "¿Quién es EMP-0004?"}
# Render despierta un servicio dormido del plan gratuito en hasta un minuto
TIMEOUT_SECONDS = 90


def check(
    name: str, expected: int, request: Callable[[], httpx.Response]
) -> bool:
    """Hace una petición e imprime si su código coincide con el esperado.

    :param name: Nombre de la comprobación que se imprime
    :type name: str
    :param expected: Código HTTP esperado
    :type expected: int
    :param request: Función sin argumentos que hace la petición
    :type request: Callable[[], httpx.Response]
    :return: ``True`` si el código coincide
    :rtype: bool
    """
    try:
        status = request().status_code
    except httpx.HTTPError as error:
        # Solo el tipo de error: el mensaje podría traer datos de la petición
        print(f"  [FAIL] {name} -> {type(error).__name__} (esperado {expected})")
        return False
    passed = status == expected
    label = "OK" if passed else "FAIL"
    print(f"  [{label}] {name} -> {status} (esperado {expected})")
    return passed


def smoke(url: str, key: str, client: httpx.Client) -> bool:
    """Corre las tres comprobaciones contra ``url``.

    :param url: URL base del servicio, sin barra final
    :type url: str
    :param key: Clave de un cliente válido
    :type key: str
    :param client: Cliente HTTP (inyectable en pruebas)
    :type client: httpx.Client
    :return: ``True`` si las tres pasan
    :rtype: bool
    """
    results = [
        check("GET /health", 200, lambda: client.get(f"{url}/health")),
        check(
            "POST /ask sin clave",
            401,
            lambda: client.post(f"{url}/ask", json=QUESTION),
        ),
        check(
            "POST /ask con clave",
            200,
            lambda: client.post(
                f"{url}/ask", json=QUESTION, headers={"X-API-Key": key}
            ),
        ),
    ]
    return all(results)


def main(args: list[str]) -> int:
    """Lee la URL y la clave y corre la prueba de humo.

    :param args: Argumentos de la línea de comandos, sin el nombre del script
    :type args: list[str]
    :return: Código de salida
    :rtype: int
    """
    key = os.environ.get("SMOKE_API_KEY", "")
    if len(args) != 1 or not key:
        print("Uso: SMOKE_API_KEY=<clave> python scripts/smoke.py <url>")
        return 2
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        passed = smoke(args[0].rstrip("/"), key, client)
    print("[OK] smoke" if passed else "[FAIL] smoke")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
