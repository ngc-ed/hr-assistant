# Arquitectura del HR Assistant (sesiones 1 a 4 y reto de producción)

Asistente de Recursos Humanos que responde preguntas sobre empleados desde una página
web. API FastAPI sin estado, un solo agente con bucle con tope y un modelo detrás de una
interfaz. Observabilidad (sesión 2), palancas de costo (sesión 3) y acceso por clave,
límite de peticiones y compliance (sesión 4). El reto de producción agrega PII
enmascarada, validación de salida, reintentos, varios workers, tablero y métricas de
negocio. Decisiones en `adr/` (0013 a 0015 nuevas; 0016 del tablero queda pendiente).

```mermaid
flowchart LR
    U[Personal de RH] --> W["Página web<br/>index.html<br/>X-API-Key en sessionStorage"]
    U -- "GET /dashboard<br/>sin clave, HTML sin cifras" --> DB["Tablero<br/>dashboard.html<br/>pide la clave, sessionStorage<br/>sondea /metrics cada 5 s"]
    W -- "POST /ask" --> MW["Middleware<br/>request_id, latencia<br/>auth, rate limit"]
    DB -- "GET /metrics<br/>X-API-Key" --> MW
    MW --> M["API FastAPI<br/>app/main.py<br/>uvicorn x WEB_CONCURRENCY"]
    M -- "pregunta e historial" --> PII["PII<br/>app/pii.py<br/>enmascara entrada"]
    PII -- "texto enmascarado" --> A["Agente<br/>app/agent.py"]
    A --> L["LanguageModel<br/>app/llm.py"]
    L -.-> G["GatewayModel<br/>app/gateway.py<br/>reintentos 0.5, 1, 2 s"]
    G -- "HTTPS" --> CF[("Cloudflare AI Gateway")]
    A --> D["EmployeeDirectory"]
    A -- "respuesta" --> OG["Validación de salida<br/>app/output_guard.py<br/>enmascara y revisa"]
    OG -- "200 respuesta o mensaje seguro" --> W
    PII -- "pii_detected" --> LG["JsonLogger<br/>stdout, una línea JSON"]
    OG -- "pii_detected, output_rejected" --> LG
    MW --> ME["Metrics por proceso<br/>app/metrics.py<br/>negocio, PII, caché"]
    M --> ME
    ME -- "cifras solo con clave válida" --> DB
    A -. "metadatos: request_id, client,<br/>route, model, cost_usd" .-> T["Tracing<br/>entradas y salidas ocultas"]
    T -.-> LS[("LangSmith")]
    CI["CI: style, unit, e2e, docker"] --> R["Render<br/>render.yaml<br/>WEB_CONCURRENCY"]
    R --> M
```

## Módulos nuevos del reto

| Módulo | Responsabilidad |
| --- | --- |
| `app/pii.py` | Detecta y enmascara PII; devuelve texto y conteos por tipo |
| `app/output_guard.py` | Valida la respuesta: vacía, larga, PII, clave |
| `app/gateway.py` (ampliado) | Reintentos ante timeout y 5xx con espera inyectada |
| `app/metrics.py` (ampliado) | Métricas de negocio, rutas, caché y PII por tipo |
| `app/static/dashboard.html` | Página pública sin cifras ni clave; pide la clave, la guarda en `sessionStorage` y lee `/metrics` con `X-API-Key` |

## Límites conocidos

- Con varios workers, `/metrics`, el límite de peticiones y la caché son por proceso.
  Cada petición ve las cifras de un solo worker (README).
- El `request_id` es UUID por petición, distinto entre procesos.
- `GET /dashboard` es público pero no contiene datos: las cifras solo salen de `/metrics`, que exige clave.
