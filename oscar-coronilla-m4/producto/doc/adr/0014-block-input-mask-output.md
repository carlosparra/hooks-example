# 0014. Bloquear la entrada y enmascarar la salida

Estado: propuesto

## Contexto

La PII puede llegar en la pregunta, en el historial o en lo que inventa el modelo. Si se deja
pasar la de entrada, ya la vio el proveedor del modelo; si se bloquea la de salida, la persona
se queda sin respuesta por algo que no escribió. Además, el modelo puede responder vacío o
demasiado largo.

## Decisión

Entrada: con `PII_DETECTION=true`, `AskService` revisa la pregunta y todo el historial (antes
de la ventana) y, si hay PII, lanza `SensitiveDataError`, que se responde
`422 {"detail": "sensitive data detected: <tipos>", "request_id"}` sin llamar al modelo.
Salida: `guardrails.validate_output` aplica, en este orden, vacío -> mensaje de tope de pasos,
enmascarado (`[EMAIL]`, `[PHONE]`, ...) y recorte a `OUTPUT_MAX_CHARS`. La respuesta suma
`pii_masked` con los tipos. Con `ENVIRONMENT=production`, compliance exige `PII_DETECTION=true`.

## Consecuencias

- Ningún dato de la persona llega al modelo; el modelo nunca devuelve uno sin máscara.
- Enmascarar antes de recortar evita dejar medio dato visible.
- Una pregunta bloqueada consume cuota del límite por cliente.
- `AskResponse` gana un campo; los clientes previos lo ignoran.
