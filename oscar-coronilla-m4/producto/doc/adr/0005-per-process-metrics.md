# 0005. Métricas en memoria por proceso

Estado: propuesto

## Contexto

Se pide `GET /metrics` con peticiones, tasa de error, latencia p50/p95, tokens y si se cumple
el SLO (`SLO_P95_MS`). El ADR 0001 dice que la API no guarda nada entre peticiones y que
escalar es correr más copias.

## Decisión

Cada proceso lleva sus propias métricas en un objeto `Metrics` inyectado en `create_app`,
protegido con un candado y con una ventana acotada de latencias. `/metrics` informa solo ese
proceso e incluye su `pid`. Las métricas son de diagnóstico: ninguna respuesta de `/ask`
depende de ellas, por lo que el ADR 0001 se mantiene. El p95 se calcula por rango más cercano
y `met` es `p95 < SLO_P95_MS`.

## Consecuencias

- Sin dependencias nuevas ni almacén compartido; las pruebas inyectan un `Metrics` limpio.
- Con varias copias, cada una reporta lo suyo; para una vista global hay que juntar los
  `/metrics` (o los logs) por fuera.
- Reiniciar el proceso pone las métricas en cero; la memoria usada es fija.
