# Plan del HR Assistant (reto: PII y validación de salida)

Fuente: `spec/01` a `spec/05-pii.md`, el código actual de `product/` y
`verification/contract/test_contract_05.py`. Se parte del producto de la sesión 4, que funciona;
todo lo nuevo se agrega sin romperlo. ADR 0001 a 0012 siguen vigentes; nuevos: 0013 detector de
PII local que solo devuelve tipos, 0014 bloquear la entrada y enmascarar la salida (con su orden
de validación), 0015 auditoría de PII sin valores.

Dueños: `qa-unit` escribe `tests/` (primero, en rojo); `security` escribe `app/`,
`README.md`, `.env.example` y `doc/compliance-checklist.md`; `qa-e2e` escribe `e2e/`. `deploy`
no participa: `PII_DETECTION` vale `true` por omisión, así que `render.yaml`, el CI y el
contenedor no cambian.

## Módulos

Nuevos en `product/app/`:

- `pii.py`: patrones compilados por tipo; `detect(text) -> tuple[str, ...]` (tipos únicos en
  orden fijo `email, phone, curp, rfc, card, clabe`, nunca valores); `detect_all(texts)` une los
  tipos de varios textos; `mask(text) -> MaskResult(text, types)` reemplaza cada dato por
  `[EMAIL]`, `[PHONE]`, etc.; `luhn_ok(digits)`. Sin red ni dependencias nuevas.
- `guardrails.py`: `validate_output(text, max_chars, pii_enabled) -> GuardedAnswer(text,
  masked_types)`: vacío o solo espacios -> `STEP_LIMIT_ANSWER`; después enmascara; al final
  recorta a `OUTPUT_MAX_CHARS`. `SensitiveDataError(types)` (excepción de la entrada).

Existentes (cambian):

- `config.py`: `pii_detection` (`true`/`false`, por omisión `true`; otro valor falla) y
  `output_max_chars` (entero >= 1, por omisión 2000).
- `compliance.py`: regla `RULE_PII_ON` («PII_DETECTION must be 'true' in production»).
- `main.py`: `AskService.answer` revisa pregunta e historial completo antes de la ventana y
  antes del modelo; si hay PII emite `pii_detected` (`where=input`), suma `pii_blocked` y lanza
  `SensitiveDataError`. Tras el agente pasa la respuesta por `validate_output`; si hubo
  enmascarado emite `pii_detected` (`where=output`) y suma `pii_masked`. `AskResponse` suma
  `pii_masked: list[str]`. Nuevo manejador: `SensitiveDataError` -> `422 {"detail":
  "sensitive data detected: email, phone", "request_id"}` (tipos separados por `, `).
  `/metrics` agrega `pii_blocked` y `pii_masked` al nivel superior, como `cost_usd`.
- `metrics.py`: `add_pii_blocked()`, `add_pii_masked()` y `pii_counts()`, aparte de `snapshot`
  para no cambiar la forma de la sesión 2.
- `tracing.py`: `wrap(..., pii_types=None)` agrega `pii_types` a los metadatos (en las tres
  clases). Se registra un tramo `pii_input` o `pii_output` cuya única entrada son los tipos.
- `static/index.html`: en un `422` cuyo `detail` es texto y empieza con «sensitive data
  detected» muestra «Tu pregunta contiene datos sensibles; elimínalos y vuelve a intentar»; el
  `422` de Pydantic (lista) conserva su mensaje. No pinta respuesta del modelo.
- `README.md`, `.env.example`, `doc/compliance-checklist.md`: `PII_DETECTION`,
  `OUTPUT_MAX_CHARS` y la regla nueva (regla, archivo y función, prueba).

## Flujo de una pregunta

1. La página manda `POST /ask` con `X-API-Key` y `{question, history}`.
2. El middleware fija `request_id` y `t0`.
3. `require_client` (401) y `RateLimiter` (429), igual que en la sesión 4. Una pregunta
   bloqueada por PII sí consume cuota.
4. Pydantic valida el cuerpo (422 de validación, como antes).
5. Con `PII_DETECTION=true`, `pii.detect_all` revisa la pregunta y todos los mensajes del
   historial (antes de recortar la ventana). Si hay tipos: evento `pii_detected` (`request_id`,
   `client`, `where=input`, `types`), `pii_blocked += 1`, tramo `pii_input` con los tipos y
   `422` con `request_id`. No se llama al modelo ni se escribe `agent_run`.
6. Sin PII: ventana, ruta, agente y costo como en la sesión 3.
7. `validate_output`: si la respuesta está vacía se usa `STEP_LIMIT_ANSWER`; se enmascara la
   PII (si la detección está encendida); se recorta a `OUTPUT_MAX_CHARS`.
8. Si se enmascaró algo: `pii_detected` con `where=output`, `pii_masked += 1` y tramo
   `pii_output`. `agent_run` suma `pii_masked` (tipos).
9. Respuesta con `pii_masked` (lista vacía si no hubo); el middleware escribe `request`.
10. La página pinta la respuesta, o el mensaje de datos sensibles, 401, 429 o error.

## Pruebas

Escenarios Gherkin nuevos (`tests/features/pii.feature`, `TestClient`, modelo falso que cuenta
sus llamadas):

- Pregunta con correo -> `422`, `detail` empieza con `sensitive data detected: email`, trae
  `request_id`, el cuerpo no contiene el correo y el modelo no se llamó.
- Teléfono (`442 123 4567`, `+52 442-123-4567`), CURP, RFC, tarjeta válida y CLABE -> `422`
  con su tipo; varios tipos juntos -> todos, en orden fijo.
- PII solo en el historial -> `422`, aunque quede fuera de la ventana.
- `¿Quién es EMP-0004?` -> `200`, «Jorge Díaz» y `pii_masked == []`.
- Modelo que responde con un correo y un teléfono -> `200`, `[EMAIL]` y `[PHONE]` en la
  respuesta, `pii_masked == ["email", "phone"]`, ningún valor en la respuesta.
- Modelo con respuesta vacía -> mensaje de tope de pasos; respuesta larga -> recortada a
  `OUTPUT_MAX_CHARS`.
- Log: `pii_detected` con `where` y `types`; ningún evento contiene el dato.
- `/metrics` muestra `pii_blocked` y `pii_masked` crecientes.
- Con `PII_DETECTION=false` (desarrollo) la pregunta con correo pasa.
- Con `production` y `PII_DETECTION=false` no arranca; con `true` sí.
- Todos los escenarios de las sesiones 1 a 4 siguen pasando.

Pruebas unitarias:

- `pii`: un positivo y un negativo por tipo; `EMP-0004`, fechas (`2019-03-04`), montos y
  `request_id` no son PII; tarjeta que falla Luhn no es `card`; 18 dígitos es `clabe` (no
  `card`); RFC dentro de una CURP no se cuenta como `rfc`; `mask` reemplaza todos los valores y
  los tipos salen sin repetir; `detect` nunca devuelve el valor.
- `guardrails`: vacío y solo espacios, recorte exacto, el enmascarado ocurre antes del recorte.
- `config`: `PII_DETECTION=si` falla; `OUTPUT_MAX_CHARS=0` y `abc` fallan; valores por omisión.
- `compliance`: la regla nueva sola y junto a otras; en `development` no exige nada.
- `metrics`, `tracing` (metadatos con `pii_types`), y página: contiene el texto de datos
  sensibles.

Punta a punta (`qa-e2e`, máximo 6): pregunta con un correo muestra el mensaje de datos
sensibles y no aparece ninguna respuesta del modelo.

Meta: cobertura de 80 % o más; `unit`, `contract`, `qa`, `e2e` y `evaluate` en verde; después,
`production <url>`.

## Riesgos

- Filtrar el dato al registrarlo: `detect` y `mask` solo devuelven tipos; el `detail`, los
  eventos, las métricas y las trazas solo llevan tipos; los tramos `pii_input`/`pii_output`
  reciben los tipos como única entrada, nunca el texto. Una prueba busca el valor en todo el log.
- Falsos positivos que bloquean preguntas legítimas (fechas, `EMP-0004`, números cortos): cada
  patrón exige su largo exacto y límites `(?<![\w])`/`(?![\w])`; el teléfono cuenta 10 dígitos
  (12 con `52`); se prueban casos negativos.
- Choques entre tipos: se enmascara del más largo al más corto (`email`, `curp`, `rfc`,
  `clabe`, `card`, `phone`); 18 dígitos seguidos son `clabe`.
- Expresiones lentas con historiales grandes: patrones sin cuantificadores anidados; el
  historial no tiene tope de tamaño, así que se revisa con regex lineales.
- Recortar antes de enmascarar dejaría medio dato visible: siempre se enmascara primero.
- La PII que llega por herramientas (argumentos del `audit`): con la entrada limpia el modelo no
  la recibe del usuario y el directorio no tiene correos ni teléfonos; queda fuera del alcance.
- Trazas en desarrollo con `HIDE_OUTPUTS=false` podrían llevar la respuesta sin enmascarar del
  tramo `llm`: en producción compliance exige ocultarlas.
- Romper las sesiones previas: `pii_masked` es un campo nuevo, las fixtures conservan sus
  valores y `PII_DETECTION=true` no afecta preguntas limpias.
- Confundir el `422` de PII con el de Pydantic en la página: se distingue por el tipo de
  `detail` (texto contra lista).
- Apagar la detección en producción: compliance lo impide al arrancar.
