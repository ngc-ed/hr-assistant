# 0018. Guardián de entrada contra inyección de prompt

Estado: aceptado

## Contexto

Una pregunta puede intentar cambiar las instrucciones del modelo. Detectarlo con otro modelo costaría dinero y
sería menos predecible, y el texto de la pregunta no debe llegar al log.

## Decisión

`app/input_guard.py` (función `blocked_phrase`) corre antes de todo, también antes del enmascarado de PII y de
cualquier llamada al modelo (incluido el pequeño del supervisor). `main.py` lo invoca en `_block_injection`
sobre la pregunta y el historial. Normaliza el texto (minúsculas, sin acentos) y lo compara con una lista
cerrada de frases («ignora tus instrucciones», «prompt del sistema», «actúa como»). Si coincide, `/ask`
responde `400` con «La pregunta no se puede procesar.» y registra `input_blocked` con la frase que coincidió,
nunca con el texto de la pregunta. Si pasa, sigue el enmascarado como hoy.

## Consecuencias

- Costo cero y comportamiento determinista, fácil de probar.
- Una lista de frases no detiene sinónimos ni otros idiomas: es una capa más, junto con las herramientas de solo
  lectura por especialista y el revisor.
- Puede haber falsos positivos con preguntas legítimas que usen esas frases; la lista se mantiene corta.
- Como corre antes del enmascarado, la frase del motivo viene de la lista y no de la pregunta, así que no
  filtra PII.
