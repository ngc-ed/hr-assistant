# 0017. Pipeline de cuatro etapas con supervisor por reglas

Estado: aceptado

## Contexto

Un solo agente con dos herramientas mezcla decisiones, permisos y validación. Se quiere separar
responsabilidades, limitar qué herramienta puede usar cada parte y mantener bajo el costo y la latencia.

## Decisión

Cada pregunta pasa por guardián, supervisor, especialista y revisor, en ese orden. Las etapas se orquestan en
`app/main.py` (`/ask`); no hay un módulo `pipeline`. Guardián (`app/input_guard.py`) y revisor (`_safe_answer`
en `app/main.py`, con `app/output_guard.py`) son código (sin modelo). El supervisor (`app/supervisor.py`) elige
con reglas (id `EMP-xxxx`, departamento, persona) y solo si ninguna aplica pregunta al modelo pequeño; una
respuesta fuera de `employee` o `department` va a `employee`. Hay dos especialistas (`app/specialists.py`),
cada uno con su prompt y una sola herramienta: `employee` con `get_employee`, `department` con
`search_by_department`. `/ask` devuelve `specialist` y `agents`, y cada etapa es un run en LangSmith.

## Consecuencias

- Un especialista no puede llamar la herramienta del otro: se reduce lo que una inyección puede lograr.
- Los casos claros no pagan una llamada extra al modelo; los ambiguos sí.
- Las reglas son predecibles y probables sin modelo, pero pueden equivocarse con preguntas raras.
- La pregunta de un empleado cuyo nombre coincide con un departamento depende del orden de reglas.
- `/ask` queda stateless (ADR 0001): las etapas viven dentro de la petición.
- Como `main.py` concentra la orquestación, crece con cada etapa; separarla en un módulo queda como mejora.
