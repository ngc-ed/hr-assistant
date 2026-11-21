# 0019. Datos desde el código: la herramienta se llama antes del modelo

Estado: aceptado

## Contexto

En producción el modelo pequeño respondió «necesito utilizar la herramienta get_employee» en vez de pedirla con el
JSON, y el agente tomó ese texto como respuesta final. `agent.employee` tenía una sola `model_call` y ninguna
herramienta. Las pruebas no lo veían porque el modelo simulado siempre pedía la herramienta. Cuando el supervisor
decide por reglas (ADR 0017) el dato ya se conoce: el id `EMP-xxxx`, el departamento o la persona.

## Decisión

Si `method` es `rules`, el código llama a la herramienta del especialista antes del modelo y le pasa el resultado
como `"Resultado de la herramienta: ..."`; el modelo solo redacta. `tools_used` lleva esa herramienta y el
`audit` se registra igual, con argumentos enmascarados. Si `method` es `model`, el especialista sigue como antes y el
modelo pide la herramienta. Como red de seguridad, el revisor cambia la respuesta por «No encontré datos para
responder. Pregunta por un id como EMP-0001 o por un departamento.» y registra `output_rejected` con el motivo
`no_tool_data` cuando `tools_used` va vacío o la respuesta menciona `get_employee` o `search_by_department`. Los
demás motivos conservan el mensaje seguro de siempre. El modo `FAKE_MODEL_MODE=no_tools` (solo con
`MODEL_PROVIDER=fake`) reproduce el error en pruebas.

## Consecuencias

- El caso común ya no depende de que un modelo pequeño formatee bien un JSON: menos vueltas y menos costo.
- La respuesta de un dato real nunca sale sin una herramienta ejecutada.
- Una persona nombrada que no se resuelve a un único empleado cae al camino del modelo y puede llegar al revisor.
- Una pregunta sin id ni departamento que el modelo responde sin herramienta (por ejemplo un saludo) recibe el
  mensaje `no_tool_data`; es un costo aceptado.
- El revisor busca los nombres de las herramientas en el texto: una respuesta legítima que los cite se rechaza.
- `FAKE_MODEL_MODE` no se despliega: no va en `render.yaml`.
