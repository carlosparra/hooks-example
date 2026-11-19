# 0002. Interfaz de modelo con protocolo JSON y modelo simulado

Estado: propuesto

## Contexto

Se quiere cambiar de proveedor de modelo sin tocar el agente y probar sin red ni costo. En
esta sesión solo existe el modelo simulado.

## Decisión

`llm.py` define la interfaz `complete(messages)` que devuelve el texto del modelo y los
tokens de entrada y salida. El modelo siempre responde un único objeto JSON:
`{"tool", "args"}` o `{"answer"}`. `FakeLanguageModel` implementa reglas deterministas y se
elige con `MODEL_PROVIDER=fake`. `create_app()` recibe el modelo por inyección.

## Consecuencias

- Agregar un proveedor real es una clase nueva y una rama en la fábrica de modelos.
- Las pruebas son deterministas e inyectan modelos guionizados.
- El agente debe tolerar JSON inválido de un modelo real futuro sin caerse.
