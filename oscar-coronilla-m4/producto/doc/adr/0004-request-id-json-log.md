# 0004. Id por petición y log JSON de una línea por evento, sin textos

Estado: propuesto

## Contexto

Soporte necesita responder "qué pasó con la petición X" con datos. Las preguntas y respuestas
contienen datos personales de empleados, y el log suele terminar en sistemas con más acceso
que la aplicación.

## Decisión

Un middleware ASGI, por fuera de todo, asigna a cada petición un `request_id` (el de
`X-Request-ID` si es válido, 1 a 128 caracteres de `[A-Za-z0-9._:-]`; si no, un UUID) y lo
devuelve en el encabezado. Los eventos (`request`, `agent_run`, `audit`, `error`) se escriben
como una línea JSON en la salida estándar con `ts` (UTC, de un reloj inyectado), `service`,
`event` y `request_id`. Nunca se registra el texto de la pregunta ni de la respuesta, ni el
mensaje de una excepción: solo conteos, nombres de herramienta, sus `args` y el tipo de error.

## Consecuencias

- Se puede seguir una petición de punta a punta filtrando por `request_id`.
- El log sirve para auditoría (qué herramientas y con qué argumentos) sin exponer el diálogo.
- Diagnosticar un error requiere reproducirlo: el log no trae el mensaje completo.
- Un id de cliente con formato extraño se reemplaza, lo que protege el log de inyecciones.
