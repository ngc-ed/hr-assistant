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

from app.agent import Agent, AgentResult
from app.auth import extract_api_key_from_header, validate_api_key
from app.clock import Clock, SystemClock
from app.config import Settings, load_settings
from app.costs import PriceTable
from app.directory import EmployeeDirectory
from app.gateway import MODEL_UNAVAILABLE_MESSAGE, ModelUnavailableError
from app.levers import Route, choose_model, window_history
from app.llm import LanguageModel, build_models
from app.logs import JsonLogger
from app.metrics import Metrics
from app.rate_limiter import RateLimiter
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
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json"}
CLIENT_REQUEST_KEY = "client"


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
    """

    settings: Settings
    models: dict[str, LanguageModel]
    prices: PriceTable
    directory: EmployeeDirectory


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
    """

    route: Route
    history_sent: int
    result: AgentResult
    cost_usd: float


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
            status_code=422,
            detail=(
                "question must have at most "
                f"{settings.max_question_chars} characters"
            ),
        )


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

    def audit(tool: str, args: dict) -> None:
        """Deja una línea ``audit`` por cada herramienta ejecutada."""
        observability.logger.log(
            "audit", request_id, client=client, action="tool_call", tool=tool, args=args
        )

    route = choose_model(body.question, settings)
    history = window_history(
        [message.model_dump() for message in body.history], settings.history_window
    )
    # Un agente por petición: no hay estado compartido entre hilos.
    agent = Agent(
        assistant.models[route.model],
        assistant.directory,
        max_steps=settings.agent_max_steps,
    )
    with observability.tracing.context(request_id, client):
        result = agent.run(body.question, history, on_tool_call=audit)
    cost_usd = assistant.prices.cost_usd(
        route.model, result.billable_input_tokens, result.billable_output_tokens
    )
    return _RunReport(
        route=route, history_sent=len(history), result=result, cost_usd=cost_usd
    )


def _register_routes(
    app: FastAPI,
    assistant: _Assistant,
    observability: _Observability,
    page: str,
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
    """

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        """Sirve la página web."""
        return page

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
        _check_question_length(body, assistant.settings)
        request_id = request.state.request_id
        client = getattr(request.state, CLIENT_REQUEST_KEY, None)
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
        _log_agent_run(observability.logger, request_id, body, report, client=client)
        return AskResponse(
            answer=result.answer,
            steps=result.steps,
            tools_used=result.tools_used,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=request_id,
            model=report.route.model,
            route=report.route.reason,
            cached_calls=result.cached_calls,
            cost_usd=report.cost_usd,
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
        settings=settings, models=models, prices=prices, directory=directory
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
    _register_routes(app, assistant, observability, page)
    return app


app = create_app()
