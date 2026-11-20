# 0003. Un solo agente con bucle con tope y protocolo JSON

Estado: aceptado

## Contexto

El agente decide en varias vueltas si pide una herramienta o responde. Sin límite, un
modelo que nunca responde gasta tiempo y tokens sin fin.

## Decisión

Un solo agente con dos herramientas de solo lectura (`get_employee`,
`search_by_department`). El modelo responde un objeto JSON: `{"tool", "args"}` o
`{"answer"}`. El resultado de cada herramienta vuelve como mensaje `user` que empieza
con `Resultado de la herramienta: `. El bucle se detiene en `AGENT_MAX_STEPS` (por
omisión 3) y entonces responde exactamente `No pude completar la respuesta. Intenta
con una pregunta más concreta.` JSON mal formado o herramienta desconocida se
devuelven al modelo como resultado de error y cuentan como una vuelta.

## Consecuencias

- El costo por pregunta está acotado y es predecible.
- Preguntas que necesiten más vueltas que el tope fallan con un mensaje claro.
- Las herramientas no modifican datos: no hay riesgo de efectos secundarios.
