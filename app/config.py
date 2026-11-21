"""Configuración del HR Assistant leída de variables de entorno."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.auth import parse_api_keys

GATEWAY_PROVIDER = "gateway"
SUPPORTED_PROVIDERS = ("fake", GATEWAY_PROVIDER)
DEFAULT_MODEL_PROVIDER = "fake"
DEFAULT_AGENT_MAX_STEPS = 3
DEFAULT_MAX_QUESTION_CHARS = 2000
DEFAULT_MAX_ANSWER_CHARS = 2000
DEFAULT_EMPLOYEES_PATH = "data/employees.json"
DEFAULT_SERVICE_NAME = "hr-assistant"
DEFAULT_SLO_P95_MS = 2000
DEFAULT_CF_GATEWAY_ID = "default"
DEFAULT_MODEL_SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
DEFAULT_MODEL_LARGE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
DEFAULT_ROUTER_MAX_CHARS = 80
DEFAULT_HISTORY_WINDOW = 6
DEFAULT_MODEL_MAX_TOKENS = 300
DEFAULT_MODEL_TEMPERATURE = 0.0
DEFAULT_CACHE_TTL_SECONDS = 0
DEFAULT_PRICES_PATH = "data/model_prices.json"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
DEFAULT_MODEL_MAX_RETRIES = 2
MIN_API_KEY_LENGTH = 16
BOOLEAN_VALUES = {"true": True, "false": False}


class ConfigError(ValueError):
    """Error de configuración: un valor inválido impide arrancar."""


@dataclass(frozen=True)
class Settings:  # pylint: disable=too-many-instance-attributes
    """Configuración inmutable del producto.

    :param model_provider: Proveedor del modelo (``fake`` o ``gateway``)
    :type model_provider: str
    :param agent_max_steps: Tope de vueltas del bucle del agente
    :type agent_max_steps: int
    :param max_question_chars: Largo máximo de la pregunta
    :type max_question_chars: int
    :param employees_path: Ruta del archivo de empleados
    :type employees_path: str
    :param service_name: Valor del campo ``service`` del log
    :type service_name: str
    :param slo_p95_ms: Meta de latencia p95 en milisegundos
    :type slo_p95_ms: int
    :param tracing_enabled: Si se mandan trazas a LangSmith (bandera y clave)
    :type tracing_enabled: bool
    :param hide_inputs: No mandar entradas a LangSmith
    :type hide_inputs: bool
    :param hide_outputs: No mandar salidas a LangSmith
    :type hide_outputs: bool
    :param cf_account_id: Cuenta de Cloudflare
    :type cf_account_id: str
    :param cf_gateway_id: Id del AI Gateway
    :type cf_gateway_id: str
    :param cf_api_token: Token de Cloudflare (secreto, fuera de ``repr``)
    :type cf_api_token: str
    :param model_small: Nombre del modelo barato
    :type model_small: str
    :param model_large: Nombre del modelo capaz
    :type model_large: str
    :param routing: Si se elige el modelo por pregunta
    :type routing: bool
    :param router_max_chars: Preguntas más largas van al modelo capaz
    :type router_max_chars: int
    :param history_window: Mensajes de historial que se mandan al modelo
    :type history_window: int
    :param model_max_tokens: Tope de tokens de salida por llamada
    :type model_max_tokens: int
    :param model_temperature: Temperatura del modelo
    :type model_temperature: float
    :param cache_ttl_seconds: Segundos de caché del gateway (0: apagada)
    :type cache_ttl_seconds: int
    :param prices_path: Ruta del archivo de precios por modelo
    :type prices_path: str
    :param environment: Ambiente: ``development`` o ``production``
    :type environment: str
    :param api_keys: Diccionario {cliente: clave} (secreto, fuera de ``repr``)
    :type api_keys: dict[str, str] | None
    :param rate_limit_per_minute: Máximo de peticiones por cliente por minuto
    :type rate_limit_per_minute: int
    :param langsmith_api_key: Clave de LangSmith (secreto, fuera de ``repr``)
    :type langsmith_api_key: str
    :param model_max_retries: Reintentos ante timeout o 5xx del gateway
    :type model_max_retries: int
    :param max_answer_chars: Largo máximo de una respuesta válida
    :type max_answer_chars: int
    :param fake_model_mode: Modo del modelo simulado (``no_tools``); solo para
        pruebas y solo se lee con ``MODEL_PROVIDER=fake``
    :type fake_model_mode: str
    """

    model_provider: str = DEFAULT_MODEL_PROVIDER
    agent_max_steps: int = DEFAULT_AGENT_MAX_STEPS
    max_question_chars: int = DEFAULT_MAX_QUESTION_CHARS
    employees_path: str = DEFAULT_EMPLOYEES_PATH
    service_name: str = DEFAULT_SERVICE_NAME
    slo_p95_ms: int = DEFAULT_SLO_P95_MS
    tracing_enabled: bool = False
    hide_inputs: bool = True
    hide_outputs: bool = True
    cf_account_id: str = ""
    cf_gateway_id: str = DEFAULT_CF_GATEWAY_ID
    # Los tokens son secretos: no aparecen en ``repr`` ni en logs.
    cf_api_token: str = field(default="", repr=False)
    model_small: str = DEFAULT_MODEL_SMALL
    model_large: str = DEFAULT_MODEL_LARGE
    routing: bool = True
    router_max_chars: int = DEFAULT_ROUTER_MAX_CHARS
    history_window: int = DEFAULT_HISTORY_WINDOW
    model_max_tokens: int = DEFAULT_MODEL_MAX_TOKENS
    model_temperature: float = DEFAULT_MODEL_TEMPERATURE
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
    prices_path: str = DEFAULT_PRICES_PATH
    environment: str = DEFAULT_ENVIRONMENT
    api_keys: dict[str, str] | None = None
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    langsmith_api_key: str = field(default="", repr=False)
    model_max_retries: int = DEFAULT_MODEL_MAX_RETRIES
    max_answer_chars: int = DEFAULT_MAX_ANSWER_CHARS
    fake_model_mode: str = ""


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    """Lee un entero positivo de ``env``.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor si la variable no está
    :type default: int
    :return: El entero leído
    :rtype: int
    :raises ConfigError: Si el valor no es un entero positivo
    """
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as error:
        message = f"{name} must be a positive integer, got {raw!r}"
        raise ConfigError(message) from error
    if value <= 0:
        raise ConfigError(f"{name} must be a positive integer, got {raw!r}")
    return value


def _boolean(env: Mapping[str, str], name: str, default: bool) -> bool:
    """Lee un booleano ``true``/``false`` de ``env`` sin distinguir mayúsculas.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor si la variable no está
    :type default: bool
    :return: El booleano leído
    :rtype: bool
    :raises ConfigError: Si el valor no es ``true`` ni ``false``
    """
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = BOOLEAN_VALUES.get(raw.strip().lower())
    if value is None:
        raise ConfigError(f"{name} must be true or false, got {raw!r}")
    return value


def _non_negative_int(env: Mapping[str, str], name: str, default: int) -> int:
    """Lee un entero mayor o igual que cero de ``env``.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor si la variable no está
    :type default: int
    :return: El entero leído
    :rtype: int
    :raises ConfigError: Si el valor no es un entero mayor o igual que cero
    """
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    message = f"{name} must be an integer >= 0, got {raw!r}"
    try:
        value = int(raw.strip())
    except ValueError as error:
        raise ConfigError(message) from error
    if value < 0:
        raise ConfigError(message)
    return value


def _non_negative_float(env: Mapping[str, str], name: str, default: float) -> float:
    """Lee un número real mayor o igual que cero de ``env``.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor si la variable no está
    :type default: float
    :return: El número leído
    :rtype: float
    :raises ConfigError: Si el valor no es un número mayor o igual que cero
    """
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    message = f"{name} must be a number >= 0, got {raw!r}"
    try:
        value = float(raw.strip())
    except ValueError as error:
        raise ConfigError(message) from error
    # ``isfinite`` rechaza también ``nan`` e ``inf``.
    if not math.isfinite(value) or value < 0:
        raise ConfigError(message)
    return value


def _text(env: Mapping[str, str], name: str, default: str) -> str:
    """Lee un texto de ``env``; si falta o está vacío, usa ``default``.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor si la variable no está o está vacía
    :type default: str
    :return: El texto sin espacios en los extremos
    :rtype: str
    """
    return (env.get(name) or "").strip() or default


def _cloudflare(env: Mapping[str, str], provider: str) -> dict:
    """Lee las variables ``CF_*`` y exige las tres si el proveedor es ``gateway``.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param provider: Proveedor del modelo ya validado
    :type provider: str
    :return: ``cf_account_id``, ``cf_gateway_id`` y ``cf_api_token``
    :rtype: dict
    :raises ConfigError: Si falta una variable con ``gateway`` (nunca su valor)
    """
    raw_gateway = env.get("CF_GATEWAY_ID")
    values = {
        "CF_ACCOUNT_ID": (env.get("CF_ACCOUNT_ID") or "").strip(),
        # Ausente usa el valor por omisión; presente pero vacía cuenta como falta.
        "CF_GATEWAY_ID": (
            DEFAULT_CF_GATEWAY_ID if raw_gateway is None else raw_gateway.strip()
        ),
        "CF_API_TOKEN": (env.get("CF_API_TOKEN") or "").strip(),
    }
    if provider == GATEWAY_PROVIDER:
        for name, value in values.items():
            if not value:
                raise ConfigError(f"{name} is required when MODEL_PROVIDER=gateway")
    return {
        "cf_account_id": values["CF_ACCOUNT_ID"],
        "cf_gateway_id": values["CF_GATEWAY_ID"] or DEFAULT_CF_GATEWAY_ID,
        "cf_api_token": values["CF_API_TOKEN"],
    }


def _levers(env: Mapping[str, str]) -> dict:
    """Lee los modelos y las palancas de costo.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :return: Campos de ``Settings`` de modelos, palancas y precios
    :rtype: dict
    :raises ConfigError: Si algún valor es inválido
    """
    return {
        "model_small": _text(env, "MODEL_SMALL", DEFAULT_MODEL_SMALL),
        "model_large": _text(env, "MODEL_LARGE", DEFAULT_MODEL_LARGE),
        "routing": _boolean(env, "ROUTING", True),
        "router_max_chars": _positive_int(
            env, "ROUTER_MAX_CHARS", DEFAULT_ROUTER_MAX_CHARS
        ),
        "history_window": _non_negative_int(
            env, "HISTORY_WINDOW", DEFAULT_HISTORY_WINDOW
        ),
        "model_max_tokens": _positive_int(
            env, "MODEL_MAX_TOKENS", DEFAULT_MODEL_MAX_TOKENS
        ),
        "model_temperature": _non_negative_float(
            env, "MODEL_TEMPERATURE", DEFAULT_MODEL_TEMPERATURE
        ),
        "model_max_retries": _non_negative_int(
            env, "MODEL_MAX_RETRIES", DEFAULT_MODEL_MAX_RETRIES
        ),
        "cache_ttl_seconds": _non_negative_int(
            env, "CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS
        ),
        "prices_path": _text(env, "PRICES_PATH", DEFAULT_PRICES_PATH),
    }


def _validate_production_compliance(
    settings_dict: dict, env: Mapping[str, str]
) -> None:
    """Valida reglas de compliance en producción.

    Se rechaza si alguna regla falla. Los errores nunca exponen claves
    ni tokens.

    :param settings_dict: Configuración siendo construida
    :type settings_dict: dict
    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :raises ValueError: Si alguna regla de compliance falla
    """
    # Regla 1: API_KEYS no vacía y claves >= 16 caracteres
    api_keys_str = (env.get("API_KEYS") or "").strip()
    if not api_keys_str:
        raise ValueError(
            "ENVIRONMENT=production requires API_KEYS to be set and non-empty"
        )

    api_keys = parse_api_keys(api_keys_str)
    for client, key in api_keys.items():
        if len(key) < MIN_API_KEY_LENGTH:
            raise ValueError(
                f"ENVIRONMENT=production requires all API keys to have at "
                f"least {MIN_API_KEY_LENGTH} characters; key for client "
                f"{client!r} has {len(key)} characters"
            )
    settings_dict["api_keys"] = api_keys

    # Regla 2: MODEL_PROVIDER no es fake
    if settings_dict["model_provider"].lower() == "fake":
        raise ValueError(
            "ENVIRONMENT=production does not allow MODEL_PROVIDER=fake"
        )

    # Regla 3: Si hay clave de LangSmith, HIDE_INPUTS y HIDE_OUTPUTS
    # deben ser true (independientemente del flag de tracing)
    has_tracing_key = bool((env.get("LANGSMITH_API_KEY") or "").strip())
    if has_tracing_key:
        if not settings_dict["hide_inputs"]:
            raise ValueError(
                "ENVIRONMENT=production with LANGSMITH_API_KEY requires "
                "HIDE_INPUTS=true"
            )
        if not settings_dict["hide_outputs"]:
            raise ValueError(
                "ENVIRONMENT=production with LANGSMITH_API_KEY requires "
                "HIDE_OUTPUTS=true"
            )


def load_settings(env: Mapping[str, str]) -> Settings:
    """Construye la configuración a partir de variables de entorno.

    :param env: Variables de entorno (por ejemplo ``os.environ``)
    :type env: Mapping[str, str]
    :return: La configuración validada
    :rtype: Settings
    :raises ConfigError: Si algún valor es inválido
    :raises ValueError: Si la compliance de producción falla
    """
    provider = (env.get("MODEL_PROVIDER") or DEFAULT_MODEL_PROVIDER).strip()
    if provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(SUPPORTED_PROVIDERS)
        raise ConfigError(
            f"MODEL_PROVIDER {provider!r} is not supported (use: {supported})"
        )
    employees_path = (env.get("EMPLOYEES_PATH") or DEFAULT_EMPLOYEES_PATH).strip()
    service_name = (env.get("SERVICE_NAME") or "").strip() or DEFAULT_SERVICE_NAME
    has_tracing_key = bool((env.get("LANGSMITH_API_KEY") or "").strip())
    langsmith_key = (env.get("LANGSMITH_API_KEY") or "").strip()
    tracing_flag = _boolean(env, "LANGSMITH_TRACING", False)
    environment = (env.get("ENVIRONMENT") or DEFAULT_ENVIRONMENT).strip()

    # Construir diccionario de configuración
    settings_dict = {
        **_cloudflare(env, provider),
        **_levers(env),
        "model_provider": provider,
        "agent_max_steps": _positive_int(
            env, "AGENT_MAX_STEPS", DEFAULT_AGENT_MAX_STEPS
        ),
        "max_question_chars": _positive_int(
            env, "MAX_QUESTION_CHARS", DEFAULT_MAX_QUESTION_CHARS
        ),
        "employees_path": employees_path,
        "service_name": service_name,
        "slo_p95_ms": _positive_int(env, "SLO_P95_MS", DEFAULT_SLO_P95_MS),
        "tracing_enabled": tracing_flag and has_tracing_key,
        "hide_inputs": _boolean(env, "HIDE_INPUTS", True),
        "hide_outputs": _boolean(env, "HIDE_OUTPUTS", True),
        "environment": environment,
        "rate_limit_per_minute": _positive_int(
            env, "RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE
        ),
        "langsmith_api_key": langsmith_key,
        "max_answer_chars": _positive_int(
            env, "MAX_ANSWER_CHARS", DEFAULT_MAX_ANSWER_CHARS
        ),
        # Solo se lee con el proveedor simulado; con otro se ignora.
        "fake_model_mode": (
            (env.get("FAKE_MODEL_MODE") or "").strip().lower()
            if provider == "fake"
            else ""
        ),
    }

    # Parsear API_KEYS en desarrollo (sin validación strict)
    api_keys_str = (env.get("API_KEYS") or "").strip()
    if api_keys_str:
        settings_dict["api_keys"] = parse_api_keys(api_keys_str)

    # Validar compliance en producción
    if environment.lower() == "production":
        _validate_production_compliance(settings_dict, env)

    return Settings(**settings_dict)
