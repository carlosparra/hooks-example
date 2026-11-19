# 0011. Límite de peticiones por cliente, en memoria del proceso

Estado: propuesto

## Contexto

Un cliente con clave válida podría disparar el costo del modelo. El límite debe probarse sin
esperar un minuto real y sin agregar infraestructura (Redis) a un servicio gratuito de una sola
instancia.

## Decisión

`ratelimit.py` guarda, por cliente autenticado, las marcas del reloj inyectado (`Clock`) de los
últimos 60 segundos, con un candado. Si ya hay `RATE_LIMIT_PER_MINUTE` marcas, `require_client`
responde `429 {"detail": "rate limit exceeded"}` con `Retry-After` en segundos enteros (hacia
arriba, mínimo 1). Se revisa después de la clave, así que una clave inventada nunca crea una
cubeta.

## Consecuencias

- Las pruebas avanzan el reloj falso y verifican el `Retry-After` exacto.
- Como las métricas (ADR 0005), el límite es por proceso: con varias instancias cada una cuenta
  aparte, y un reinicio lo vacía. Si se escala, se cambia por un almacén compartido.
- La memoria está acotada por el número de clientes configurados.
