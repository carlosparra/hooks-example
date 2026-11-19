# Evidencia · Concurrencia y límite por cliente

Pruebas contra el producto publicado en Render (`https://hr-assistant-oscar.onrender.com`), con el modelo real
(Cloudflare Workers AI a través de AI Gateway). Fecha: 16 de noviembre de 2026.

Herramienta: `scripts/load_test.py`. Manda varias preguntas a la vez a `POST /ask` y reporta los códigos, la
latencia, el tiempo total y el costo. La clave se lee de la variable `SMOKE_API_KEY`, nunca del comando.

## Cómo se corrió

```powershell
$env:SMOKE_API_KEY = Read-Host "Clave (sin el cliente)"
uv run python scripts/load_test.py https://hr-assistant-oscar.onrender.com 20 10
# esperar 60 segundos
uv run python scripts/load_test.py https://hr-assistant-oscar.onrender.com 40 10
uv run python scripts/load_test.py https://hr-assistant-oscar.onrender.com 40 10
Remove-Item Env:SMOKE_API_KEY
```

## Resultados

| Corrida | Peticiones (concurrencia) | Códigos | Tiempo total | Latencia de las 200 | Costo del lote |
| --- | --- | --- | --- | --- | --- |
| A · Concurrencia | 20 (10 a la vez) | 20 × 200 | 2.90 s (6.9 peticiones/s) | p50 1313 ms, p95 1711 ms, máx. 1898 ms | 0.000769 USD |
| B · Límite por cliente | 40 (10 a la vez) | 30 × 200, 10 × 429 | 4.29 s (9.3 peticiones/s) | p50 1086 ms, p95 1663 ms, máx. 1770 ms | 0.001167 USD |
| C · Mismo minuto que B | 40 (10 a la vez) | 40 × 429 | 0.93 s | (ninguna 200) | 0.000000 USD |

## Qué demuestra

- **Concurrencia (A).** La API sin estado atiende 20 peticiones simultáneas con el modelo real y sin errores. El
  p95 (1711 ms) queda por debajo del SLO de 2000 ms (`SLO_P95_MS`).
- **Límite por cliente (B).** Con `RATE_LIMIT_PER_MINUTE=30`, el servicio responde exactamente 30 peticiones y
  rechaza el resto con `429` y el encabezado `Retry-After`.
- **El límite también controla el costo (C).** Las peticiones rechazadas no llegan al modelo: 40 respuestas `429`
  costaron 0 USD. Un cliente que abusa, o un script descontrolado, no puede gastar más de 30 respuestas por minuto.
- **Costo real por respuesta.** 20 respuestas costaron 0.000769 USD: unos 0.00004 USD por pregunta con el modelo
  real.

## Límites conocidos (trade-offs)

- **El límite es por proceso** (ADR 0011). Con una sola instancia en Render es exacto; si el servicio escalara a
  varias instancias, cada una contaría por separado. La solución sería un almacén compartido, como Redis.
- **El plan gratuito de Render duerme el servicio** con la inactividad. La prueba despierta el servicio con
  `/health` antes de medir, para que el arranque en frío no distorsione la latencia.

## Pendiente

- Repetir la corrida A sobre la versión final, después de publicar la detección de PII.

17 de noviembre de 2026, después de publicar la detección de PII:

| Corrida | Peticiones (concurrencia) | Códigos | Tiempo total | Latencia de las 200 | Costo del lote |
| --- | --- | --- | --- | --- | --- |
| A · Concurrencia | 20 (10 a la vez) | 20 × 200 | 2.61 s (7.7 peticiones/s) | p50 1150 ms, p95 1465 ms, máx. 1519 ms | 0.000779 USD |

La detección de PII en la entrada y en la salida no degradó el servicio: el p95 bajó de 1711 ms a 1465 ms
(la variación se debe al modelo y a la red) y sigue por debajo del SLO de 2000 ms.
