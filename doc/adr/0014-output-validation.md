# 0014. Validar la salida del modelo antes de devolverla

Estado: aceptado

## Contexto

La respuesta del modelo no es de fiar: puede venir vacía, ser enorme, repetir datos
personales o filtrar algo parecido a una clave.

## Decisión

`app/output_guard.py` revisa la respuesta, ya enmascarada, con cuatro reglas en este
orden: vacía (`empty`), más larga que `MAX_ANSWER_CHARS` (`too_long`), con PII que
sobrevive al enmascarado (`pii`) y con forma de clave (`secret`: `sk-...`, `Bearer ...`
o cadena larga aleatoria). Si falla, `/ask` responde `200` con «No pude generar una
respuesta segura. Intenta de nuevo.» y registra `output_rejected` con el motivo, nunca
con el texto. Los campos `cost_usd` y tokens se conservan: la llamada ya se hizo.

## Consecuencias

- El rechazo es `200` y no `5xx`: no sube `error_rate` y la página muestra un mensaje usable.
- Se paga la llamada aunque se rechace la respuesta; no hay regeneración automática.
- La regla de cadena aleatoria puede rechazar ids largos legítimos; se ajusta por umbral
  de longitud y se prueba con respuestas reales del directorio.
- El motivo es una lista cerrada, así que el log no puede filtrar contenido.
