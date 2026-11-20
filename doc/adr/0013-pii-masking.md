# 0013. Enmascarar datos personales antes y después del modelo

Estado: aceptado

## Contexto

Las preguntas pueden traer correo, teléfono, RFC, CURP, NSS o tarjeta. Esos valores no
deben llegar al modelo externo, ni al log, ni a las trazas, ni a un mensaje de error.
Las respuestas también pueden repetirlos.

## Decisión

Un módulo único, `app/pii.py`, detecta con expresiones regulares y cambia cada valor por
`[CORREO]`, `[TELEFONO]`, `[RFC]`, `[CURP]`, `[NSS]` o `[TARJETA]`. Se aplica a la
pregunta y al historial antes de crear el agente, y a la respuesta antes de devolverla.
Devuelve el texto limpio y un conteo por tipo, nunca los valores. Cada detección escribe
`pii_detected` con `pii_type`, `count` y `direction` (`input` u `output`) y suma a
`pii_by_type` en las métricas. Las expresiones se aplican de lo más específico a lo más
general (tarjeta, CURP, RFC, correo, NSS, teléfono) para que un patrón no consuma a otro.

## Consecuencias

- El modelo trabaja con texto enmascarado; si la persona pregunta por un correo, el
  modelo ve `[CORREO]` y no puede buscarlo. Se acepta: la búsqueda es por id o departamento.
- Un dato legítimo del directorio (por ejemplo un correo de empleado) también se
  enmascara en la respuesta; es el costo de la regla simple.
- Las expresiones regulares dan falsos positivos y negativos; se cubren con pruebas por tipo.
- La métrica `pii_by_type` es por proceso, como el resto (ADR 0005).
