"""Prueba de concurrencia contra el producto publicado o local.

Manda varias preguntas a la vez a ``POST /ask`` y reporta los códigos de
respuesta, la latencia p50 y p95, el tiempo total y el costo. Sirve como
evidencia de que la API sin estado atiende peticiones simultáneas, y de que el
límite por cliente responde 429 cuando se pasa.

Uso: ``uv run python scripts/load_test.py <url> [total] [concurrencia]``

La clave se lee de la variable ``SMOKE_API_KEY``: nunca del comando ni del chat.
"""

import asyncio
import os
import statistics
import sys
import time
from collections import Counter

import httpx

QUESTIONS = [
    "¿Quién es EMP-0001?",
    "¿Quién es EMP-0004?",
    "¿Quiénes trabajan en Finanzas?",
    "¿Qué puesto tiene EMP-0005?",
]


async def one_request(client, semaphore, index):
    """Hace una pregunta y devuelve su código, su latencia y su costo.

    :param client: Cliente HTTP con la URL base y la clave
    :type client: httpx.AsyncClient
    :param semaphore: Limita cuántas peticiones van a la vez
    :type semaphore: asyncio.Semaphore
    :param index: Número de la petición, para rotar las preguntas
    :type index: int
    :return: Código HTTP, milisegundos y costo en USD
    :rtype: tuple[int, float, float]
    """
    question = QUESTIONS[index % len(QUESTIONS)]
    async with semaphore:
        start = time.perf_counter()
        response = await client.post("/ask", json={"question": question})
        elapsed_ms = (time.perf_counter() - start) * 1000
    cost = 0.0
    if response.status_code == 200:
        cost = response.json().get("cost_usd", 0.0)
    return response.status_code, elapsed_ms, cost


def percentile(values, fraction):
    """Devuelve el percentil ``fraction`` (entre 0 y 1) de ``values``."""
    ordered = sorted(values)
    position = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[position]


async def run(url, key, total, concurrency):
    """Despierta el servicio y lanza ``total`` peticiones, ``concurrency`` a la vez.

    :return: Los resultados de cada petición y los segundos totales
    :rtype: tuple[list[tuple[int, float, float]], float]
    """
    semaphore = asyncio.Semaphore(concurrency)
    headers = {"X-API-Key": key}
    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=90) as client:
        # Render duerme el servicio gratuito: la primera petición lo despierta
        await client.get("/health")
        start = time.perf_counter()
        results = await asyncio.gather(
            *(one_request(client, semaphore, i) for i in range(total))
        )
        wall = time.perf_counter() - start
    return list(results), wall


def report(results, wall, concurrency):
    """Imprime el resumen y devuelve ``True`` si no hubo errores inesperados.

    Un 429 es esperado si se pasa el límite por cliente; cualquier 5xx o 401 no.
    """
    codes = Counter(code for code, _, _ in results)
    latencies = [ms for code, ms, _ in results if code == 200]
    cost = sum(value for _, _, value in results)
    print(f"Peticiones: {len(results)} (de {concurrency} en {concurrency})")
    print(f"Códigos: {dict(sorted(codes.items()))}")
    print(f"Tiempo total: {wall:.2f} s ({len(results) / wall:.1f} peticiones/s)")
    if latencies:
        print(
            f"Latencia de las 200: p50={statistics.median(latencies):.0f} ms "
            f"p95={percentile(latencies, 0.95):.0f} ms max={max(latencies):.0f} ms"
        )
    print(f"Costo del lote: {cost:.6f} USD")
    unexpected = {code: n for code, n in codes.items() if code not in (200, 429)}
    if codes.get(429):
        print(f"[INFO] {codes[429]} respuestas 429: el límite por cliente funcionó")
    print("[OK] load_test" if not unexpected else f"[FAIL] load_test {unexpected}")
    return not unexpected


def main(args):
    """Lee los argumentos y la clave, corre la prueba y devuelve el código."""
    key = os.environ.get("SMOKE_API_KEY", "")
    if not args or not key:
        print("Uso: SMOKE_API_KEY=<clave> python scripts/load_test.py <url> "
              "[total] [concurrencia]")
        return 2
    total = int(args[1]) if len(args) > 1 else 20
    concurrency = int(args[2]) if len(args) > 2 else 10
    results, wall = asyncio.run(run(args[0].rstrip("/"), key, total, concurrency))
    return 0 if report(results, wall, concurrency) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
