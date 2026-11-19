# 0009. Costo por respuesta con una tabla de precios local

Estado: propuesto

## Contexto

Para decidir si una palanca sirve hay que medir el costo de cada respuesta, también con el
modelo simulado. Los precios cambian y no deben estar escritos en el código.

## Decisión

`pricing.py` lee `PRICES_PATH` (copia de `spec/model_prices.json`, USD por millón de
tokens). El costo de una respuesta es la suma, por llamada no cacheada, de entrada por precio
de entrada más salida por precio de salida del modelo elegido. No se redondea. La respuesta de
`POST /ask` lleva `model`, `route`, `cached_calls` y `cost_usd`; `agent_run` los registra y
`/metrics` acumula `cost_usd` por proceso (ADR 0005). Si `MODEL_SMALL` o `MODEL_LARGE` no tienen
precio, la aplicación no arranca.

## Consecuencias

- Actualizar precios es editar un archivo, sin desplegar código.
- Con `fake` el costo es aproximado (tokens por palabras), pero sirve para comparar palancas.
- El costo es una estimación local; la factura real la da Cloudflare.
- Las llamadas con `HIT` cuentan sus tokens pero no su costo.
