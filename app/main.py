"""API web sin estado del HR Assistant (ADR 0001).

Observable (ADR 0004 a 0006) y con palancas de costo (ADR 0007 a 0009).
Seguro y con límites de peticiones (sesión 4).
"""

import os
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.agent import AgentResult
from app.auth import extract_api_key_from_header, validate_api_key
from app.clock import Clock, SystemClock
from app.config import Settings, load_settings
from app.costs import PriceTable
from app.directory import EmployeeDirectory
from app.gateway import MODEL_UNAVAILABLE_MESSAGE, ModelUnavailableError
from app.input_guard import BLOCKED_MESSAGE, BLOCKED_STATUS, blocked_phrase
from app.levers import Route, choose_model, window_history
from app.lifecycle import exit_with_parent
from app.llm import LanguageModel, build_models
from app.logs import JsonLogger
from app.metrics import Metrics
from app.output_guard import SAFE_ANSWER, asked_ids, rejection_reason
from app.pii import mask_pii
from app.rate_limiter import RateLimiter
from app.specialists import EMPLOYEE, build_specialist
from app.supervisor import METHOD_RULES, Supervisor
from app.tracing import Tracing

PRODUCT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = Path(__file__).resolve().parent / "static" / "index.html"
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")
INTERNAL_ERROR_STATUS = 500
INTERNAL_ERROR_DETAIL = "internal error"
MODEL_UNAVAILABLE_STATUS = 502
MILLISECONDS_PER_SECOND = 1000
LATENCY_DECIMALS = 3
# Rutas públicas que no requieren clave
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/dashboard"}
CLIENT_REQUEST_KEY = "client"
UNKNOWN_DEPARTMENT = "desconocido"
QUESTION_TOO_LONG_STATUS = 422
DASHBOARD_PATH = Path(__file__).resolve().parent / "static" / "dashboard.html"


class HistoryMessage(BaseModel):
    """Un turno anterior de la conversación, enviado por el cliente.

    :param role: ``user`` o ``assistant``
    :type role: str
    :param content: Texto del turno
    :type content: str
    """

    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    """Cuerpo de ``POST /ask``.

    :param question: Pregunta de la persona (no vacía)
    :type question: str
    :param history: Turnos anteriores (opcional)
    :type history: list[HistoryMessage]
    """

    question: str
    history: list[HistoryMessage] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        """Rechaza preguntas vacías o solo con espacios.

        :param value: Pregunta recibida
        :type value: str
        :return: La pregunta sin espacios en los extremos
        :rtype: str
        :raises ValueError: Si la pregunta queda vacía
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be empty")
        return stripped


class AskResponse(BaseModel):
    """Respuesta de ``POST /ask``; ``request_id`` sirve para pedir soporte.

    ``model`` y ``route`` dicen qué modelo respondió y por qué; ``cost_usd`` es el
    costo de las llamadas no cacheadas.
    """

    answer: str
    steps: int
    tools_used: list[str]
    input_tokens: int
    output_tokens: int
    request_id: str
    model: str
    route: str
    cached_calls: int
    cost_usd: float
    specialist: str
    agents: list[str]


@dataclass(frozen=True)
class _Observability:
    """Piezas de observabilidad que comparten el middleware y las rutas.

    :param clock: Reloj inyectado para medir latencias
    :type clock: Clock
    :param logger: Log JSON de eventos
    :type logger: JsonLogger
    :param metrics: Métricas en memoria del proceso
    :type metrics: Metrics
    :param tracing: Contexto de trazas de LangSmith
    :type tracing: Tracing
    """

    clock: Clock
    logger: JsonLogger
    metrics: Metrics
    tracing: Tracing


@dataclass(frozen=True)
class _Assistant:
    """Piezas compartidas que usa ``/ask`` para crear un agente por petición.

    :param settings: Configuración del producto
    :type settings: Settings
    :param models: Modelos por nombre (``MODEL_SMALL`` y ``MODEL_LARGE``)
    :type models: dict[str, LanguageModel]
    :param prices: Precios por modelo
    :type prices: PriceTable
    :param directory: Directorio de empleados
    :type directory: EmployeeDirectory
    :param supervisor: Supervisor que elige al especialista
    :type supervisor: Supervisor
    """

    settings: Settings
    models: dict[str, LanguageModel]
    prices: PriceTable
    directory: EmployeeDirectory
    supervisor: Supervisor


@dataclass(frozen=True)
class _RunReport:
    """Lo que se sabe de una corrida del agente para el log y la respuesta.

    :param route: Modelo elegido y motivo
    :type route: Route
    :param history_sent: Mensajes de historial que se mandaron al modelo
    :type history_sent: int
    :param result: Resultado del agente
    :type result: AgentResult
    :param cost_usd: Costo de la respuesta en USD
    :type cost_usd: float
    :param department: Departamento consultado (``desconocido`` si no hubo)
    :type department: str
    """

    route: Route
    history_sent: int
    result: AgentResult
    cost_usd: float
    department: str = UNKNOWN_DEPARTMENT
    specialist: str = EMPLOYEE
    method: str = METHOD_RULES


def _resolve_request_id(candidate: str | None) -> str:
    """Usa el id del cliente si tiene forma segura; si no, genera un UUID.

    :param candidate: Valor del encabezado ``X-Request-ID`` (puede faltar)
    :type candidate: str | None
    :return: El id de la petición
    :rtype: str
    """
    if candidate is not None and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid.uuid4())


def _add_request_middleware(app: FastAPI, observability: _Observability) -> None:
    """Agrega el middleware que da id, mide, registra y atrapa errores.

    :param app: Aplicación a la que se agrega
    :type app: FastAPI
    :param observability: Reloj, log, métricas y trazas
    :type observability: _Observability
    """

    @app.middleware("http")
    async def observe_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Envuelve cada petición: id, latencia, log ``request`` y ``error``."""
        started = observability.clock.monotonic()
        request_id = _resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except HTTPException:
            # FastAPI maneja HTTPException, no capturar
            raise
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Solo el tipo: el mensaje podría traer datos personales.
            observability.logger.log(
                "error", request_id, error_type=type(error).__name__
            )
            response = JSONResponse(
                status_code=INTERNAL_ERROR_STATUS,
                content={"detail": INTERNAL_ERROR_DETAIL, "request_id": request_id},
            )
        elapsed = observability.clock.monotonic() - started
        latency_ms = round(elapsed * MILLISECONDS_PER_SECOND, LATENCY_DECIMALS)
        observability.metrics.record_request(response.status_code, latency_ms)
        observability.logger.log(
            "request",
            request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _add_auth_middleware(
    app: FastAPI,
    settings: Settings,
    rate_limiter: RateLimiter,
) -> None:
    """Agrega middleware de autenticación y rate limit para rutas protegidas.

    :param app: Aplicación a la que se agrega
    :type app: FastAPI
    :param settings: Configuración con API_KEYS
    :type settings: Settings
    :param rate_limiter: Limiter de peticiones por cliente
    :type rate_limiter: RateLimiter
    """

    @app.middleware("http")
    async def authenticate_and_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Valida clave y rate limit para rutas protegidas."""
        # Rutas públicas no requieren autenticación
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Si no hay claves configuradas, no pedir autenticación
        if not settings.api_keys:
            return await call_next(request)

        # Extraer y validar clave
        api_key = extract_api_key_from_header(request.headers)
        try:
            client = validate_api_key(api_key, settings.api_keys)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )

        # Verificar rate limit
        try:
            rate_limiter.check_rate_limit(client)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers or {},
            )

        # Guardar cliente en el estado
        request.state.client = client

        return await call_next(request)


def _log_agent_run(
    logger: JsonLogger, request_id: str, body: AskRequest, report: _RunReport,
    client: str | None = None,
) -> None:
    """Escribe ``agent_run`` con conteos, nunca con el texto de la conversación.

    :param logger: Log JSON de eventos
    :type logger: JsonLogger
    :param request_id: Id de la petición
    :type request_id: str
    :param body: Cuerpo de la petición (solo se cuentan sus partes)
    :type body: AskRequest
    :param report: Ruta, historial enviado, resultado y costo de la corrida
    :type report: _RunReport
    :param client: Nombre del cliente (opcional)
    :type client: str | None
    """
    result = report.result
    logger.log(
        "agent_run",
        request_id,
        client=client,
        question_chars=len(body.question),
        history_messages=len(body.history),
        history_sent=report.history_sent,
        steps=result.steps,
        tools=list(result.tools_used),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        stopped=result.stopped,
        model=report.route.model,
        route=report.route.reason,
        cached_calls=result.cached_calls,
        cost_usd=report.cost_usd,
    )


def _check_question_length(body: AskRequest, settings: Settings) -> None:
    """Rechaza con ``422`` las preguntas más largas que el máximo.

    :param body: Cuerpo de la petición
    :type body: AskRequest
    :param settings: Configuración (largo máximo de la pregunta)
    :type settings: Settings
    :raises HTTPException: Si la pregunta pasa del máximo
    """
    if len(body.question) > settings.max_question_chars:
        raise HTTPException(
            status_code=QUESTION_TOO_LONG_STATUS,
            detail=(
                "question must have at most "
                f"{settings.max_question_chars} characters"
            ),
        )


def _log_pii(
    logger: JsonLogger,
    request_id: str,
    counts: dict[str, int],
    direction: str,
    client: str | None = None,
) -> None:
    """Escribe un ``pii_detected`` por tipo, con conteo y sin el valor.

    :param logger: Log JSON de eventos
    :type logger: JsonLogger
    :param request_id: Id de la petición
    :type request_id: str
    :param counts: Detecciones por tipo
    :type counts: dict[str, int]
    :param direction: ``input`` u ``output``
    :type direction: str
    :param client: Nombre del cliente (opcional)
    :type client: str | None
    """
    for pii_type, count in counts.items():
        logger.log(
            "pii_detected", request_id, client=client,
            pii_type=pii_type, count=count, direction=direction,
        )


def _mask_request(body: AskRequest) -> tuple[AskRequest, dict[str, int]]:
    """Enmascara la pregunta y el historial antes de que lleguen al modelo.

    :param body: Cuerpo original de la petición
    :type body: AskRequest
    :return: El cuerpo enmascarado y las detecciones por tipo (sin valores)
    :rtype: tuple[AskRequest, dict[str, int]]
    """
    totals: dict[str, int] = {}
    question, counts = mask_pii(body.question)
    _add_counts(totals, counts)
    history = []
    for message in body.history:
        content, counts = mask_pii(message.content)
        _add_counts(totals, counts)
        history.append(HistoryMessage(role=message.role, content=content))
    return AskRequest(question=question, history=history), totals


def _add_counts(totals: dict[str, int], counts: dict[str, int]) -> None:
    """Suma ``counts`` a ``totals``.

    :param totals: Acumulado por tipo (se modifica)
    :type totals: dict[str, int]
    :param counts: Conteos a sumar
    :type counts: dict[str, int]
    """
    for kind, count in counts.items():
        totals[kind] = totals.get(kind, 0) + count


def _mask_args(args: dict) -> dict:
    """Enmascara con ``pii.py`` los argumentos de una herramienta para la auditoría.

    :param args: Argumentos originales
    :type args: dict
    :return: Copia con los textos enmascarados
    :rtype: dict
    """
    return {
        key: mask_pii(value)[0] if isinstance(value, str) else value
        for key, value in args.items()
    }


def _block_injection(
    body: AskRequest, observability: _Observability, request_id: str,
    client: str | None = None,
) -> None:
    """Guardián: corta la pregunta si trae una frase de inyección de prompt.

    Corre antes del enmascarado y del modelo; solo registra la frase que coincidió.

    :param body: Cuerpo sin enmascarar
    :type body: AskRequest
    :param observability: Reloj, log, métricas y trazas
    :type observability: _Observability
    :param request_id: Id de la petición
    :type request_id: str
    :param client: Nombre del cliente (opcional)
    :type client: str | None
    :raises HTTPException: ``400`` si hay una frase bloqueada
    """
    texts = [body.question] + [message.content for message in body.history]
    for text in texts:
        phrase = blocked_phrase(text)
        if phrase is not None:
            observability.logger.log(
                "input_blocked", request_id, client=client, reason=phrase
            )
            observability.metrics.record_input_blocked()
            raise HTTPException(status_code=BLOCKED_STATUS, detail=BLOCKED_MESSAGE)


def _safe_answer(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    answer: str,
    settings: Settings,
    directory: EmployeeDirectory,
    observability: _Observability,
    request_id: str,
    client: str | None = None,
    asked: frozenset[str] = frozenset(),
) -> str:
    """Revisor: enmascara y valida la respuesta; si no es segura, da el mensaje fijo.

    :param answer: Respuesta del agente
    :type answer: str
    :param settings: Configuración (largo máximo de la respuesta)
    :type settings: Settings
    :param directory: Directorio para comprobar los ids que nombra la respuesta
    :type directory: EmployeeDirectory
    :param observability: Reloj, log, métricas y trazas
    :type observability: _Observability
    :param request_id: Id de la petición
    :type request_id: str
    :param client: Nombre del cliente (opcional)
    :type client: str | None
    :param asked: Ids ``EMP-xxxx`` que la persona nombró en la conversación
    :type asked: frozenset[str]
    :return: La respuesta enmascarada o el mensaje seguro
    :rtype: str
    """
    masked, counts = mask_pii(answer)
    _log_pii(observability.logger, request_id, counts, "output", client)
    reason = rejection_reason(masked, settings.max_answer_chars, directory, asked)
    if reason is None:
        return masked
    # Solo el motivo: el texto rechazado nunca va al log.
    observability.logger.log(
        "output_rejected", request_id, client=client, reason=reason
    )
    return SAFE_ANSWER


def _tool_department(
    directory: EmployeeDirectory, tool: str, args: dict
) -> str | None:
    """Saca el departamento que consultó una herramienta.

    :param directory: Directorio de empleados
    :type directory: EmployeeDirectory
    :param tool: Nombre de la herramienta
    :type tool: str
    :param args: Argumentos de la herramienta
    :type args: dict
    :return: El departamento o ``None`` si no se puede saber
    :rtype: str | None
    """
    if tool == "search_by_department":
        return str(args.get("department", "")).strip() or None
    if tool == "get_employee":
        employee = directory.get_employee(str(args.get("employee_id", "")))
        return employee.get("department") if employee else None
    return None


def _run_agent(
    assistant: _Assistant,
    observability: _Observability,
    body: AskRequest,
    request_id: str,
    client: str | None = None,
) -> _RunReport:
    """Elige modelo y ventana, corre el agente y calcula el costo.

    :param assistant: Configuración, modelos, precios y directorio
    :type assistant: _Assistant
    :param observability: Reloj, log, métricas y trazas
    :type observability: _Observability
    :param body: Cuerpo de la petición
    :type body: AskRequest
    :param request_id: Id de la petición
    :type request_id: str
    :param client: Nombre del cliente autenticado (nunca su clave)
    :type client: str | None
    :return: Ruta, historial enviado, resultado y costo
    :rtype: _RunReport
    :raises ModelUnavailableError: Si el modelo no responde
    """
    settings = assistant.settings
    departments: list[str] = []

    def audit(tool: str, args: dict) -> None:
        """Deja una línea ``audit`` por cada herramienta ejecutada."""
        department = _tool_department(assistant.directory, tool, args)
        if department:
            departments.append(department)
        observability.logger.log(
            "audit",
            request_id,
            client=client,
            action="tool_call",
            tool=tool,
            args=_mask_args(args),
        )

    route = choose_model(body.question, settings)
    history = window_history(
        [message.model_dump() for message in body.history], settings.history_window
    )
    with observability.tracing.stage("agent.supervisor"):
        decision = assistant.supervisor.decide(body.question)
    observability.metrics.record_pipeline(decision.specialist, decision.method)
    observability.logger.log(
        "supervisor_decision",
        request_id,
        client=client,
        specialist=decision.specialist,
        method=decision.method,
    )
    # Un especialista por petición: no hay estado compartido entre hilos.
    agent = build_specialist(
        decision.specialist,
        assistant.models[route.model],
        assistant.directory,
        max_steps=settings.agent_max_steps,
    )
    with observability.tracing.context(
        request_id, client, route=route.reason, model=route.model
    ) as trace_metadata:
        with observability.tracing.stage(f"agent.{decision.specialist}"):
            result = agent.run(body.question, history, on_tool_call=audit)
        cost_usd = assistant.prices.cost_usd(
            route.model, result.billable_input_tokens, result.billable_output_tokens
        )
        # El costo solo se conoce al terminar la corrida.
        trace_metadata["cost_usd"] = cost_usd
    return _RunReport(
        route=route,
        history_sent=len(history),
        result=result,
        cost_usd=cost_usd,
        department=departments[0] if departments else UNKNOWN_DEPARTMENT,
        specialist=decision.specialist,
        method=decision.method,
    )


def _register_routes(
    app: FastAPI,
    assistant: _Assistant,
    observability: _Observability,
    page: str,
    dashboard_page: str,
) -> None:
    """Registra las rutas de la API.

    :param app: Aplicación donde se registran
    :type app: FastAPI
    :param assistant: Configuración, modelos, precios y directorio
    :type assistant: _Assistant
    :param observability: Reloj, log, métricas y trazas
    :type observability: _Observability
    :param page: HTML de la página web
    :type page: str
    :param dashboard_page: HTML del tablero
    :type dashboard_page: str
    """

    @app.get("/",response_class=HTMLResponse)
    def home() -> str:
        """Sirve la página web."""
        return page

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> str:
        """Sirve el tablero: HTML sin cifras ni clave (pública)."""
        return dashboard_page

    @app.get("/health")
    def health() -> dict:
        """Indica que el proceso está vivo y cuál es su pid."""
        return {"status": "ok", "pid": os.getpid()}

    @app.get("/metrics")
    def metrics() -> dict:
        """Devuelve las métricas de este proceso (sin contar la petición actual)."""
        return observability.metrics.snapshot(os.getpid())

    @app.post("/ask", response_model=AskResponse)
    def ask(body: AskRequest, request: Request) -> AskResponse | JSONResponse:
        """Responde una pregunta sin guardar nada entre peticiones."""
        request_id = request.state.request_id
        client = getattr(request.state, CLIENT_REQUEST_KEY, None)
        # Un run raíz por petición; cada etapa cuelga de él.
        with observability.tracing.request(request_id, client):
            return _answer(
                assistant, observability, body, request_id, client
            )

    def _answer(
        assistant: _Assistant,
        observability: _Observability,
        body: AskRequest,
        request_id: str,
        client: str | None,
    ) -> AskResponse | JSONResponse:
        """Corre las cuatro etapas del pipeline para una pregunta."""
        # El guardián corre primero: antes del enmascarado y de todo modelo.
        with observability.tracing.stage("agent.guard"):
            _block_injection(body, observability, request_id, client)
            _check_question_length(body, assistant.settings)
            # Enganche para observability: ``input_pii`` son las detecciones de la
            # pregunta y el historial, por tipo, para sumar a ``pii_by_type``.
            body, input_pii = _mask_request(body)
            _log_pii(observability.logger, request_id, input_pii, "input", client)
        try:
            report = _run_agent(assistant, observability, body, request_id, client)
        except ModelUnavailableError as error:
            # Solo el tipo: el mensaje es fijo y nunca lleva el token.
            observability.logger.log(
                "error", request_id, client=client,
                error_type=type(error).__name__
            )
            return JSONResponse(
                status_code=MODEL_UNAVAILABLE_STATUS,
                content={
                    "detail": MODEL_UNAVAILABLE_MESSAGE,
                    "request_id": request_id,
                },
            )
        result = report.result
        observability.metrics.record_tokens(result.input_tokens, result.output_tokens)
        observability.metrics.record_cost(report.cost_usd)
        observability.metrics.record_pii(input_pii)
        observability.metrics.record_question(
            report.department,
            result.tools_used,
            report.route.model,
            result.cached_calls,
        )
        _log_agent_run(observability.logger, request_id, body, report, client=client)
        with observability.tracing.stage("agent.reviewer"):
            answer = _safe_answer(
                result.answer,
                assistant.settings,
                assistant.directory,
                observability,
                request_id,
                client,
                asked_ids(body.question),
            )
        return AskResponse(
            answer=answer,
            steps=result.steps,
            tools_used=result.tools_used,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=request_id,
            model=report.route.model,
            route=report.route.reason,
            cached_calls=result.cached_calls,
            cost_usd=report.cost_usd,
            specialist=report.specialist,
            agents=["guard", "supervisor", report.specialist, "reviewer"],
        )


def _resolve_data_path(path: str) -> Path:
    """Resuelve la ruta de datos; las relativas se toman desde ``product/``.

    :param path: Ruta configurada
    :type path: str
    :return: Ruta absoluta o relativa a la raíz del producto
    :rtype: Path
    """
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PRODUCT_ROOT / candidate


def create_app(
    settings: Settings | None = None,
    model: LanguageModel | None = None,
    directory: EmployeeDirectory | None = None,
    clock: Clock | None = None,
    log_stream: TextIO | None = None,
) -> FastAPI:
    """Arma la aplicación FastAPI con sus dependencias inyectadas.

    :param settings: Configuración; si falta se lee de ``os.environ``
    :type settings: Settings | None
    :param model: Modelo para ``MODEL_SMALL`` y ``MODEL_LARGE``; si falta se crea
        uno por nombre según ``MODEL_PROVIDER``
    :type model: LanguageModel | None
    :param directory: Directorio; si falta se carga de ``EMPLOYEES_PATH``
    :type directory: EmployeeDirectory | None
    :param clock: Reloj; si falta se usa el del sistema
    :type clock: Clock | None
    :param log_stream: Flujo del log; si falta se usa la salida estándar
    :type log_stream: TextIO | None
    :return: La aplicación lista para servir
    :rtype: FastAPI
    :raises ConfigError: Si la configuración del entorno o los precios son
        inválidos
    """
    settings = settings or load_settings(os.environ)
    if directory is None:
        path = _resolve_data_path(settings.employees_path)
        directory = EmployeeDirectory.from_file(path)
    prices = PriceTable.from_file(_resolve_data_path(settings.prices_path))
    # Sin precio para un modelo configurado no se arranca.
    prices.require([settings.model_small, settings.model_large])
    if model is None:
        models = build_models(settings, directory)
    else:
        models = {settings.model_small: model, settings.model_large: model}
    assistant = _Assistant(
        settings=settings,
        models=models,
        prices=prices,
        directory=directory,
        supervisor=Supervisor(directory, models[settings.model_small]),
    )
    page = INDEX_PATH.read_text(encoding="utf-8")
    clock = clock or SystemClock()
    observability = _Observability(
        clock=clock,
        logger=JsonLogger(settings.service_name, clock, stream=log_stream),
        metrics=Metrics(settings.slo_p95_ms),
        tracing=Tracing(settings),
    )

    app = FastAPI(title="HR Assistant")
    # Autenticación y rate limit primero
    rate_limiter = RateLimiter(settings.rate_limit_per_minute, clock=clock)
    _add_auth_middleware(app, settings, rate_limiter)
    # Luego observación
    _add_request_middleware(app, observability)
    dashboard_page = DASHBOARD_PATH.read_text(encoding="utf-8")
    _register_routes(app, assistant, observability, page, dashboard_page)
    return app


app = create_app()
# Si este proceso es un worker, muere junto con su proceso padre.
exit_with_parent()
