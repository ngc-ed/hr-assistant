# 0012. Compliance como código en producción

Estado: aceptado

## Contexto

En producción (`ENVIRONMENT=production`), ciertos valores inválidos o inseguros no se
pueden permitir: el producto se niega a arrancar si no se cumplen reglas de seguridad y
privacidad.

## Decisión

Con `ENVIRONMENT=production`, el producto no arranca si:
- `MODEL_PROVIDER` es `fake` (no se usa el modelo real).
- `API_KEYS` está vacía (sin clientes autenticados).
- Alguna clave tiene menos de 16 caracteres (claves débiles).
- Existe `LANGSMITH_API_KEY` y `HIDE_INPUTS` o `HIDE_OUTPUTS` no valen `true` (riesgo de
  enviar datos personales a un tercero). El criterio real es la presencia de la clave, no
  la bandera `LANGSMITH_TRACING`: es más estricto que la especificación y la cubre.

La validación ocurre en `load_settings()`, lanza `ValueError` con mensaje claro y nunca
escribe valores secretos (dice el cliente y el largo de la clave, no su valor).

El archivo `doc/compliance-checklist.md` es una tabla con la regla, dónde está en el
código y cómo se comprueba, incluidas las reglas que aún no tienen prueba.

## Consecuencias

- Los errores de configuración se encuentran en arranque, no en la primera petición.
- Render rechaza el despliegue si el servicio no arranca por incumplir una regla.
- Las reglas son simples, sin lógica compleja, para que las pruebas sean deterministas.
- El `compliance-checklist.md` es un documento vivo que se sincroniza con el código.
