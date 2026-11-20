# 0016. Tablero público sin datos y métricas con clave

Estado: aceptado

## Contexto

El tablero debe verse desde el navegador, pero una página no puede mandar `X-API-Key` desde la URL sin
exponer la clave. A la vez, las cifras de `/metrics` no deben ser públicas.

## Decisión

`GET /dashboard` es público y entrega HTML estático sin cifras ni claves (`app/static/dashboard.html`).
La persona escribe su clave, se guarda en `sessionStorage` y la página consulta `/metrics` cada 5 s con
`X-API-Key`. `/metrics` sigue protegido por el middleware de claves (ADR 0010). Las métricas nuevas de la
spec 06 (`by_specialist`, `supervisor_decisions`, `input_blocked`) se muestran por el mismo camino.

## Consecuencias

- Nada sensible viaja en la URL ni en el HTML; sin clave solo se ve una página vacía.
- El sondeo consume el límite de peticiones del cliente (ADR 0011).
- La clave vive en `sessionStorage` mientras dure la sesión del navegador.
- Las cifras son por proceso (ADR 0005): con varios workers cada lectura ve un solo worker.
