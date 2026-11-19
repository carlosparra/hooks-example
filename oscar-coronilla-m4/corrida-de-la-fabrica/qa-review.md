APROBADO

Revisión de `product/` contra QA.md (reto de PII, primera vuelta).

`uv run python -m verification qa`: [OK] (pylint 10.00/10).

Revisé lo que el verificador no ve:

- Nombres en inglés y claros: `pii.py` (`mask`, `detect`, `detect_all`, `luhn_ok`), `guardrails.py`
  (`SensitiveDataError`, `validate_output`, `GuardedAnswer`) y los métodos nuevos de `AskService`
  (`_block_sensitive_input`, `_record_pii`).
- Configuración: `PII_DETECTION` y `OUTPUT_MAX_CHARS` se leen del entorno, se validan en
  `config.py` y están en `.env.example` y en el README. Los marcadores (`[EMAIL]`...), el prefijo
  del `422` y los códigos de estado son constantes con nombre, que es lo que pide el contrato.
- Docstrings Sphinx en todo lo público nuevo, con `:raises:` donde aplica.
- Manejo de errores: `SensitiveDataError` se convierte en `422` con `request_id` y solo los tipos;
  una respuesta vacía o que no es texto se cambia por el mensaje de tope de pasos; con
  `ENVIRONMENT=production` el producto no arranca sin `PII_DETECTION=true`.
- Log y trazas sin datos personales ni claves: `pii_detected` solo lleva `request_id`, `client`,
  `where` y `types`; la traza solo agrega `pii_types`; `output/server.log` no tiene correos,
  números largos ni claves.
- README: explica cómo correrlo, las dos variables nuevas, el `422` por datos sensibles y
  `pii_masked`.
- ADR 0013, 0014 y 0015 describen lo que hace el código; los ADR previos siguen vigentes y
  `doc/compliance-checklist.md` tiene la sección de PII con pruebas que existen.

Observación que no bloquea: `AskService.answer` en `product/app/main.py` creció con el reto
(revisa la entrada, arma mensajes, elige modelo, corre el agente, valida la salida, emite eventos
y métricas). Si vuelve a crecer, conviene separar la parte de eventos y métricas en un método
privado ("Keep functions small and focused").
