# Reporte de la fábrica: reto de PII (spec/05-pii.md)

**Estado: LISTA**

URL pública: https://hr-assistant-oscar.onrender.com

## Resumen

| Concepto | Valor |
|---|---|
| Rechazos del plan | 0 de 2 |
| Correcciones del paso 5 | 1 de 2 (avisos de pylint en `tests/`, a cargo de `qa-unit`) |
| Vueltas de QA (qa-style) | 1 de 2 (APROBADO a la primera) |
| Ciclos de triage | 0 de 2 (el humo pasó a la primera) |
| Ajustes pedidos por la persona | 2 (opciones de pylint en el CI y una prueba de precios que leía `../spec`) |
| Publicaciones | 2 (commits `1cab3e2` y `4f21e29` en `hr-assistant-oscar`) |

## Tabla de evaluate

| Variante | Calidad | Costo (USD) | Tokens de entrada |
|---|---|---|---|
| Sin palancas de costo | 100 % | 0.000867 | 1661 |
| Con palancas de costo | 100 % | 0.000114 | 1091 |

## Prueba de humo en producción

- `GET /health`: 200 (esperado 200).
- `POST /ask` sin clave: 401 (esperado 401).
- `POST /ask` con clave: 200 (esperado 200).

## Bitácora

1. Inicio: `product/app/` existe; se reinició `output/activity.jsonl`.
2. Plan: `architect` actualizó `output/plan.md`, escribió los ADR 0013 a 0015 y actualizó `doc/architecture.md`.
3. Aprobación del plan: la persona aprobó a la primera.
4. Pruebas primero: `qa-unit` escribió 25 pruebas; `verification unit` falló con código 2 (rojo esperado).
5. Especialistas en paralelo: `security` implementó `app/pii.py`, `app/guardrails.py` y la integración; `qa-e2e` agregó una prueba de punta a punta de PII.
6. Compuertas, pasada 1: `unit` y `contract` pasaron; `qa` falló por avisos de pylint en `tests/`.
7. Corrección 1: `qa-unit` corrigió los avisos sin cambiar lo que prueban.
8. Compuertas, pasada 2: `unit`, `contract`, `qa`, `e2e` y `evaluate` pasaron.
9. Evaluador-optimizador: `qa-style` dio APROBADO. Observación sin bloqueo: `AskService.answer` creció.
10. Primera petición para publicar: la persona la detuvo, porque el CI anterior falló en la etapa style (pylint 8.65/10) al no usar las mismas opciones que `verification/qa.py`.
11. `deploy` alineó la etapa style de `ci.yml` con `verification/qa.py`; las cinco compuertas pasaron de nuevo.
12. Publicación 1, aprobada por la persona: commit `1cab3e2` (26 archivos).
13. El CI falló en la etapa unit: `test_pricing.py` leía `../spec/model_prices.json`.
14. `qa-unit` hizo autocontenida esa prueba; las cinco compuertas pasaron de nuevo.
15. Publicación 2, aprobada por la persona: commit `4f21e29` (1 archivo).
16. Humo en producción: OK. Estado LISTA.

Pipeline: [output/pipeline.md](pipeline.md)
