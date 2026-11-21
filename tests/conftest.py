"""Fixtures compartidas: directorio real, configuración y cliente HTTP en memoria.

Las pruebas no levantan servidor ni usan red: arman la app con ``create_app()`` y
le inyectan sus dependencias.
"""

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.directory import EmployeeDirectory
from app.llm import Completion, FakeModel
from app.main import create_app

EMPLOYEES_PATH = Path(__file__).resolve().parent.parent / "data" / "employees.json"
FIXED_NOW = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
FIXED_STEP_SECONDS = 0.25
GATEWAY_TOKEN = "token-secreto-123"


class FixedClock:
    """Reloj de prueba: hora fija en UTC y un ``monotonic`` que avanza un paso fijo.

    :param now: Hora que devuelve siempre ``now()``
    :type now: datetime
    :param step: Segundos que avanza ``monotonic()`` en cada llamada
    :type step: float
    """

    def __init__(self, now=FIXED_NOW, step=FIXED_STEP_SECONDS):
        self._now = now
        self._step = step
        self._ticks = 100.0

    def now(self):
        """Devuelve la hora fija.

        :return: La hora fija en UTC
        :rtype: datetime
        """
        return self._now

    def monotonic(self):
        """Devuelve el contador actual y lo avanza un paso.

        :return: Segundos del contador
        :rtype: float
        """
        current = self._ticks
        self._ticks += self._step
        return current


class ScriptedModel:
    """Modelo de prueba que devuelve textos fijos en orden y recuerda lo que vio.

    :param texts: Respuestas que dará el modelo, una por llamada
    :type texts: list[str]
    """

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    def complete(self, messages):
        """Devuelve el siguiente texto del guion con tokens fijos.

        :param messages: Conversación que recibe el modelo
        :type messages: list[dict]
        :return: La respuesta del guion
        :rtype: Completion
        """
        self.calls.append([dict(message) for message in messages])
        return Completion(text=self.texts.pop(0), input_tokens=10, output_tokens=2)


class SpyModel:
    """Envuelve un modelo real y guarda los mensajes de cada llamada.

    :param inner: Modelo al que se delega la respuesta
    :type inner: object
    """

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def complete(self, messages):
        """Registra los mensajes y delega en el modelo interno.

        :param messages: Conversación que recibe el modelo
        :type messages: list[dict]
        :return: La respuesta del modelo interno
        :rtype: Completion
        """
        self.calls.append([dict(message) for message in messages])
        return self.inner.complete(messages)


@pytest.fixture
def directory():
    """El directorio de empleados del producto."""
    return EmployeeDirectory.from_file(EMPLOYEES_PATH)


@pytest.fixture
def make_client(directory):
    """Fábrica de clientes HTTP con configuración, modelo, reloj y log opcionales.

    El reloj y el flujo del log solo se pasan a ``create_app`` si la prueba los da,
    para que las pruebas de la sesión 1 sigan usando la firma original.
    """

    def _make(env=None, model=None, clock=None, log_stream=None):
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **(env or {})}
        settings = load_settings(variables)
        extra = {}
        if clock is not None:
            extra["clock"] = clock
        if log_stream is not None:
            extra["log_stream"] = log_stream
        app = create_app(
            settings=settings, model=model, directory=directory, **extra
        )
        return TestClient(app)

    return _make


@pytest.fixture
def fixed_clock():
    """Un reloj fijo nuevo para cada prueba."""
    return FixedClock()


@pytest.fixture
def scripted_model():
    """La clase ``ScriptedModel`` para armar modelos de guion en cada prueba."""
    return ScriptedModel


@pytest.fixture
def spy_model(directory):
    """Modelo simulado real envuelto en un espía."""
    return SpyModel(FakeModel(directory.departments()))


@pytest.fixture
def token():
    """El token de Cloudflare de prueba, que nunca debe aparecer en errores."""
    return GATEWAY_TOKEN


@pytest.fixture
def gateway_env():
    """Variables de entorno completas para usar el AI Gateway."""
    return {
        "MODEL_PROVIDER": "gateway",
        "CF_ACCOUNT_ID": "cuenta-1",
        "CF_GATEWAY_ID": "mi-gateway",
        "CF_API_TOKEN": GATEWAY_TOKEN,
    }


@pytest.fixture
def scenario_client(make_client, fixed_clock):
    """Crea el cliente de un escenario una sola vez, con reloj fijo y log en memoria.

    El contexto del escenario debe tener ``env``, ``model``, ``client`` y ``log``.
    """

    def _client(context):
        if context["client"] is None:
            context["client"] = make_client(
                env=context["env"],
                model=context["model"],
                clock=fixed_clock,
                log_stream=context["log"],
            )
        return context["client"]

    return _client


EMPLOYEE_TOOL = {"tool": "get_employee", "args": {"employee_id": "EMP-0004"}}
ID_QUESTION = "¿Quién es EMP-0004?"
DEPARTMENT_QUESTION = "¿Quién trabaja en Tecnología?"
UNCLEAR_QUESTION = "Cuéntame algo interesante"


def reply(payload):
    """Serializa una respuesta de guion como el JSON que espera el agente."""
    return json.dumps(payload, ensure_ascii=False)


def answer(text):
    """Una respuesta final de guion."""
    return reply({"answer": text})


def ask(client, question):
    """Hace ``POST /ask`` con una pregunta."""
    return client.post("/ask", json={"question": question})


@pytest.fixture
def setup(make_client, scripted_model, log_lines):
    """Arma ``(client, model, events)`` con un modelo de guion y un log en memoria.

    ``events()`` devuelve las líneas del log ya parseadas, con filtro opcional
    por nombre de evento.
    """

    def _build(script):
        model = scripted_model(script)
        log = io.StringIO()
        client = make_client(model=model, log_stream=log)

        def events(name=None):
            return [row for row in log_lines(log) if name in (None, row["event"])]

        events.raw = log.getvalue
        events.stream = log
        return client, model, events

    return _build


@pytest.fixture
def log_lines():
    """Función que devuelve cada línea de un log en memoria ya parseada como JSON."""

    def _parse(stream):
        return [json.loads(line) for line in stream.getvalue().splitlines()]

    return _parse
