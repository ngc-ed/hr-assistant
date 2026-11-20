# 0007. Enrutamiento por regla entre dos modelos con nombre

Estado: aceptado

## Contexto

El modelo grande cuesta unas seis veces más por token que el pequeño, y la mayoría de
las preguntas (un empleado, un departamento) no lo necesitan. Elegir el modelo con
otro modelo agregaría costo y latencia. Las palancas deben medirse sin red.

## Decisión

`app/levers.py` elige el modelo con una regla en código, en este orden: grande si
`ROUTING=false` (`routing_disabled`), si la pregunta pasa de `ROUTER_MAX_CHARS`
(`long_question`) o si contiene «compara», «resume», «explica», «por qué», «analiza»
o «todos» sin distinguir mayúsculas (`keyword:<palabra>`); pequeño en otro caso
(`simple`). Devuelve el modelo y el motivo (`route`). `build_models` crea un modelo
por nombre (`MODEL_SMALL`, `MODEL_LARGE`), también con `MODEL_PROVIDER=fake`, y el
endpoint crea un `Agent` por petición con el modelo elegido. La ventana de historial
(`HISTORY_WINDOW`, entero `>= 0`, sin tope) se aplica solo al historial del cliente,
antes del bucle; la pregunta actual siempre se manda.

## Consecuencias

- Regla barata, determinista y fácil de probar; el motivo queda en la respuesta y en
  el log para auditar decisiones.
- Una pregunta difícil sin palabra clave va al pequeño: la calidad se vigila con
  `verification evaluate` y, con el modelo real, con revisión de una persona.
- Las palabras clave coinciden como subcadena («explicación» va al grande): cuesta
  más pero no baja la calidad.
- El agente y su bucle no cambian (ADR 0002 y 0003 siguen vigentes).
