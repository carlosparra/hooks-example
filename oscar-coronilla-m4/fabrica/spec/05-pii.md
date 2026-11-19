# Reto · Detección de PII y validación de salida

Parte del producto de las sesiones 1 a 4. Agrega detección de información personal (PII) en lo que entra y en lo
que sale, sin registrar nunca el dato detectado.

## Lo que debe hacer

1. **Detector de PII** en `app/pii.py`, con expresiones regulares y sin servicios externos. Detecta:
   - `email`: correos electrónicos.
   - `phone`: teléfonos de México (10 dígitos, con o sin `+52`, espacios o guiones).
   - `curp`: CURP (18 caracteres con su formato).
   - `rfc`: RFC de persona física (13) o moral (12).
   - `card`: tarjetas de 13 a 19 dígitos que pasan el algoritmo de Luhn.
   - `clabe`: CLABE interbancaria (18 dígitos).

   Devuelve solo los **tipos** encontrados, nunca los valores. Un número de empleado (`EMP-0004`) no es PII.
2. **Entrada.** Si la pregunta o algún mensaje del historial contiene PII, `POST /ask` responde
   `422 {"detail": "sensitive data detected: <tipos separados por coma>", "request_id": ...}` y **no llama al
   modelo**. La respuesta de error nunca repite el dato.
3. **Salida.** Antes de responder, el texto del modelo se revisa. Cada dato de PII se reemplaza por `[EMAIL]`,
   `[PHONE]`, `[CURP]`, `[RFC]`, `[CARD]` o `[CLABE]`. La respuesta de `POST /ask` agrega `pii_masked` con la lista
   de tipos enmascarados (vacía si no hubo).
4. **Validación de salida.** La respuesta del modelo debe ser texto no vacío; si pasa de `OUTPUT_MAX_CHARS`, se
   recorta. Si llega vacía, se responde el mensaje de tope de pasos de la sesión 1.
5. **Auditoría.** Cada detección escribe un evento `pii_detected` con `request_id`, `client`, `where` (`input` u
   `output`) y `types`. **Nunca el valor.** `/metrics` agrega los contadores `pii_blocked` y `pii_masked`, y la traza
   lleva los tipos en sus metadatos.
6. **Página.** Con un `422` por datos sensibles muestra «Tu pregunta contiene datos sensibles; elimínalos y vuelve
   a intentar».
7. **Compliance.** Con `ENVIRONMENT=production`, el producto se niega a arrancar si `PII_DETECTION` no vale `true`.
   `doc/compliance-checklist.md` agrega las reglas de PII.

## Configuración nueva

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `PII_DETECTION` | `true` | Enciende la detección en entrada y salida |
| `OUTPUT_MAX_CHARS` | `2000` | Largo máximo de una respuesta |

## Pruebas de punta a punta (las actualiza `qa-e2e`)

- Una pregunta con un correo muestra el mensaje de datos sensibles y no aparece ninguna respuesta del modelo.

## Cómo se comprueba

- `verification unit`, `contract`, `qa`, `e2e` y `evaluate`, como en la sesión 4.
- `verification production <url>`: la prueba de humo contra Render.
