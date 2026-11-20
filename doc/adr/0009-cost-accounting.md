# 0009. Costo por respuesta con tabla de precios local

Estado: aceptado

## Contexto

Para decidir si una palanca conviene hay que medir el costo de cada respuesta, también
con el modelo simulado, y compararlo con la calidad.

## Decisión

`app/costs.py` carga `PRICES_PATH` (`data/model_prices.json`, copia de
`spec/model_prices.json`, USD por millón de tokens). Al arrancar se exige precio para
`MODEL_SMALL` y `MODEL_LARGE`; si falta, `ConfigError`. El agente suma aparte los
tokens de llamadas no cacheadas; `cost_usd = (entrada * precio_entrada + salida *
precio_salida) / 1 000 000` con el precio del modelo elegido, sin redondear. `/ask`
devuelve `model`, `route`, `cached_calls` y `cost_usd`; `agent_run` los registra y
`/metrics` agrega `cost_usd` acumulado por proceso (ADR 0005). Los modelos simulados
se cobran con el precio de su nombre; un modelo inyectado en pruebas se cobra con el
nombre de la ruta elegida.

## Consecuencias

- Las palancas se comparan sin red con `verification evaluate`.
- El costo es una estimación: los precios cambian y hay que revisar el archivo.
- Con el simulado los tokens son palabras: sirve para comparar configuraciones, no
  para presupuestar.
- Una llamada cacheada cuesta 0 aunque reporte tokens.
- La forma de `/metrics` crece con `cost_usd`; la prueba de forma exacta de la sesión
  2 se actualiza.
