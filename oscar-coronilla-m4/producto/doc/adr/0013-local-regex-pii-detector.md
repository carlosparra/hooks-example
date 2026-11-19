# 0013. Detector de PII local que solo devuelve tipos

Estado: propuesto

## Contexto

El asistente recibe texto libre y responde con texto de un modelo. Correos, teléfonos, CURP,
RFC, tarjetas o CLABE no deben llegar al modelo ni salir en una respuesta. Mandar el texto a un
servicio externo para revisarlo sería otra fuga.

## Decisión

`app/pii.py` usa expresiones regulares compiladas, sin red ni dependencias: `email`, `phone`
(10 dígitos de México, con o sin `+52`), `curp`, `rfc` (12 o 13), `card` (13 a 19 dígitos que
pasan Luhn) y `clabe` (18 dígitos). Cada patrón exige su largo exacto y límites de palabra;
18 dígitos son `clabe`; se enmascara del tipo más largo al más corto. `detect` y `mask` solo
devuelven tipos, en orden fijo y sin repetir; nunca el valor. Un número de empleado no es PII.

## Consecuencias

- Rápido, determinista y fácil de probar con casos positivos y negativos por tipo.
- No detecta nombres ni direcciones; solo formatos con estructura.
- Puede haber falsos positivos o negativos; cada uno se corrige con una prueba nueva.
