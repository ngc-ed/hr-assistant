# Arquitectura del HR Assistant (sesiones 1 a 4, reto de producción y multiagente)

Asistente de Recursos Humanos que responde preguntas sobre empleados desde una página
web. API FastAPI sin estado, un modelo detrás de una interfaz y, desde la spec 06, un pipeline
de cuatro etapas por pregunta: guardián, supervisor, especialista y revisor. Las etapas se
orquestan en `app/main.py` (no hay un módulo `pipeline`). Observabilidad
(sesión 2), palancas de costo (sesión 3), acceso por clave, límite y compliance (sesión 4),
PII, validación de salida, reintentos y tablero (reto de producción). Decisiones en `adr/`
(0016 tablero, 0017 pipeline multiagente, 0018 guardián).

```mermaid
flowchart LR
    U[Personal de RH] --> W["Página web<br/>index.html<br/>X-API-Key en sessionStorage"]
    U -- "GET /dashboard<br/>sin clave, HTML sin cifras" --> DB["Tablero<br/>dashboard.html<br/>sondea /metrics cada 5 s"]
    W -- "POST /ask" --> MW["Middleware<br/>request_id, latencia<br/>auth, rate limit 30 por omisión"]
    DB -- "GET /metrics<br/>X-API-Key" --> MW
    MW --> M["API FastAPI<br/>app/main.py<br/>orquesta las etapas<br/>uvicorn x WEB_CONCURRENCY"]
    M --> GU["1 Guardián<br/>app/input_guard.py<br/>frases de inyección"]
    GU -- "coincide: 400<br/>input_blocked, sin modelo" --> W
    GU -- "pasa" --> PII["PII<br/>app/pii.py<br/>enmascara entrada"]
    PII --> SU["2 Supervisor<br/>app/supervisor.py<br/>reglas: EMP-id, departamento, persona"]
    SU -. "solo si ninguna regla aplica" .-> LS1["Modelo pequeño<br/>MODEL_SMALL"]
    SU -- "supervisor_decision" --> SP{"Especialista<br/>app/specialists.py"}
    SP -- "employee" --> EE["3a Empleado<br/>get_employee"]
    SP -- "department" --> ED["3b Departamento<br/>search_by_department"]
    EE --> L["LanguageModel<br/>app/llm.py"]
    ED --> L
    L -.-> G["GatewayModel<br/>app/gateway.py<br/>reintentos 0.5, 1, 2 s"]
    G -- "HTTPS" --> CF[("Cloudflare AI Gateway")]
    EE --> D["EmployeeDirectory<br/>app/directory.py"]
    ED --> D
    EE --> RV["4 Revisor<br/>_safe_answer en app/main.py<br/>app/output_guard.py, PII, ids"]
    ED --> RV
    D -. "ids válidos" .-> RV
    RV -- "200 respuesta, specialist, agents<br/>o mensaje seguro" --> W
    EE -- "audit con args enmascarados" --> LG["JsonLogger<br/>stdout, una línea JSON"]
    ED -- "audit con args enmascarados" --> LG
    GU -- "input_blocked" --> LG
    SU -- "supervisor_decision" --> LG
    PII -- "pii_detected" --> LG
    RV -- "pii_detected, output_rejected<br/>invented_id" --> LG
    MW --> ME["Metrics por proceso<br/>app/metrics.py<br/>by_specialist, supervisor_decisions,<br/>input_blocked"]
    M --> ME
    ME -- "cifras solo con clave válida" --> DB
    M -. "un run por etapa:<br/>agent.guard, agent.supervisor,<br/>agent.employee o agent.department,<br/>agent.reviewer" .-> T["Tracing<br/>app/tracing.py<br/>entradas y salidas ocultas"]
    T -.-> LS[("LangSmith")]
    CI["CI: style, unit, e2e, docker"] --> R["Render<br/>render.yaml<br/>sin RATE_LIMIT_PER_MINUTE"]
    R --> M
```

## Módulos del reto de producción

| Módulo | Responsabilidad |
| --- | --- |
| `app/pii.py` | Detecta y enmascara PII; devuelve texto y conteos por tipo |
| `app/output_guard.py` | Valida la respuesta: vacía, larga, PII, clave e id `EMP-xxxx` inventado |
| `app/gateway.py` (ampliado) | Reintentos ante timeout y 5xx con espera inyectada |
| `app/metrics.py` (ampliado) | Métricas de negocio, rutas, caché y PII por tipo |
| `app/static/dashboard.html` | Página pública sin cifras ni clave; lee `/metrics` con `X-API-Key` |

## Módulos del multiagente

| Módulo | Responsabilidad |
| --- | --- |
| `app/input_guard.py` | Guardián: frases de inyección, sin acentos ni mayúsculas (`blocked_phrase`) |
| `app/supervisor.py` | Elige especialista con reglas; modelo pequeño solo si no hay regla |
| `app/specialists.py` | Prompt y herramienta única de `employee` y `department` (`build_specialist`) |
| `app/output_guard.py` | Base del revisor: motivos `empty`, `too_long`, `pii`, `secret` e `invented_id` |
| `app/main.py` | Orquesta las etapas en `/ask`: `_block_injection` (guardián), `_mask_request`, `_run_agent` (supervisor y especialista), `_safe_answer` (revisor); arma `agents` y abre un run por etapa |

## Límites conocidos

- Con varios workers, `/metrics`, el límite de peticiones y la caché son por proceso.
  Cada petición ve las cifras de un solo worker (README).
- El `request_id` es UUID por petición, distinto entre procesos.
- `GET /dashboard` es público pero no contiene datos: las cifras solo salen de `/metrics`, que exige clave.
- El guardián es una lista de frases: no detiene sinónimos ni otros idiomas.
