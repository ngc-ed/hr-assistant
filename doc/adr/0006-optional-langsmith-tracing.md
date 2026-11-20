# 0006. Trazas opcionales en LangSmith, apagadas y ocultas por omisión

Estado: aceptado

## Contexto

Para depurar al agente sirve ver cada corrida, cada llamada al modelo y cada
herramienta. LangSmith lo da con `@traceable`, pero manda datos a un servicio externo
y el producto debe funcionar igual sin clave ni red.

## Decisión

`app/tracing.py` envuelve `langsmith`. Las trazas se encienden solo si
`LANGSMITH_TRACING=true` y existe `LANGSMITH_API_KEY`; si no, se fija
`tracing_context(enabled=False)` y no se crea ningún cliente. Encendidas, cada
petición abre un contexto con `request_id` en los metadatos y un `Client` con
`hide_inputs`/`hide_outputs` según `HIDE_INPUTS`/`HIDE_OUTPUTS` (por omisión `true`).
Se decoran `Agent.run`, la llamada al modelo y la ejecución de herramientas. La clave
la lee `langsmith` del entorno: no pasa por `Settings` ni por el log.

## Consecuencias

- Por omisión no sale ningún dato del proceso; las pruebas no tocan la red.
- El `request_id` une el log (ADR 0004) con la traza.
- Con las entradas y salidas ocultas, la traza muestra estructura y tiempos, no
  contenido.
- `langsmith` pasa a ser dependencia del producto aunque las trazas estén apagadas.
