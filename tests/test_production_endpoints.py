"""Pruebas de endpoints con autenticación y rate limiting."""

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.directory import EmployeeDirectory
from app.main import create_app

EMPLOYEES_PATH = Path(__file__).resolve().parent.parent / "data" / "employees.json"


class TestPublicEndpoints:
    """Pruebas de endpoints públicos que no requieren API Key."""

    @pytest.fixture
    def client(self):
        """Cliente con configuración básica."""
        env = {"MODEL_PROVIDER": "fake"}
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **env}
        settings = load_settings(variables)
        directory = EmployeeDirectory.from_file(EMPLOYEES_PATH)
        app = create_app(settings=settings, directory=directory)
        return TestClient(app)

    def test_root_endpoint_no_auth(self, client):
        """GET / no requiere autenticación."""
        response = client.get("/")
        assert response.status_code == 200

    def test_health_endpoint_no_auth(self, client):
        """GET /health no requiere autenticación."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_docs_endpoint_no_auth(self, client):
        """GET /docs no requiere autenticación."""
        response = client.get("/docs")
        assert response.status_code in [200, 307]


class TestProtectedEndpoints:
    """Pruebas de endpoints protegidos que requieren API Key."""

    @pytest.fixture
    def client_with_auth(self):
        """Cliente con autenticación configurada."""
        env = {
            "MODEL_PROVIDER": "fake",
            "API_KEYS": "alice:secretkey123456,bob:anothersecret789",
        }
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **env}
        settings = load_settings(variables)
        directory = EmployeeDirectory.from_file(EMPLOYEES_PATH)
        app = create_app(settings=settings, directory=directory)
        return TestClient(app)

    def test_ask_endpoint_requires_auth(self, client_with_auth):
        """POST /ask requiere autenticación."""
        response = client_with_auth.post(
            "/ask",
            json={"question": "test"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid or missing API key"

    def test_ask_endpoint_with_valid_key(self, client_with_auth):
        """POST /ask con clave válida."""
        response = client_with_auth.post(
            "/ask",
            json={"question": "¿Quién es EMP-0004?"},
            headers={"X-API-Key": "secretkey123456"},
        )
        assert response.status_code == 200

    def test_ask_endpoint_with_invalid_key(self, client_with_auth):
        """POST /ask con clave inválida."""
        response = client_with_auth.post(
            "/ask",
            json={"question": "test"},
            headers={"X-API-Key": "wrongkey"},
        )
        assert response.status_code == 401

    def test_metrics_endpoint_requires_auth(self, client_with_auth):
        """GET /metrics requiere autenticación."""
        response = client_with_auth.get("/metrics")
        assert response.status_code == 401

    def test_metrics_endpoint_with_valid_key(self, client_with_auth):
        """GET /metrics con clave válida."""
        response = client_with_auth.get(
            "/metrics",
            headers={"X-API-Key": "secretkey123456"},
        )
        assert response.status_code == 200

    def test_metrics_endpoint_with_invalid_key(self, client_with_auth):
        """GET /metrics con clave inválida."""
        response = client_with_auth.get(
            "/metrics",
            headers={"X-API-Key": "wrongkey"},
        )
        assert response.status_code == 401


class TestRateLimitingEndpoints:
    """Pruebas de rate limiting en endpoints."""

    @pytest.fixture
    def client_with_rate_limit(self):
        """Cliente con rate limiting bajo."""
        env = {
            "MODEL_PROVIDER": "fake",
            "API_KEYS": "alice:secretkey123456",
            "RATE_LIMIT_PER_MINUTE": "2",
        }
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **env}
        settings = load_settings(variables)
        directory = EmployeeDirectory.from_file(EMPLOYEES_PATH)
        app = create_app(settings=settings, directory=directory)
        return TestClient(app)

    def test_ask_endpoint_rate_limit_exceeded(self, client_with_rate_limit):
        """POST /ask con rate limit excedido."""
        # Primeros 2 requests deben pasar
        response1 = client_with_rate_limit.post(
            "/ask",
            json={"question": "test 1"},
            headers={"X-API-Key": "secretkey123456"},
        )
        assert response1.status_code == 200

        response2 = client_with_rate_limit.post(
            "/ask",
            json={"question": "test 2"},
            headers={"X-API-Key": "secretkey123456"},
        )
        assert response2.status_code == 200

        # El tercer request debe fallar
        response3 = client_with_rate_limit.post(
            "/ask",
            json={"question": "test 3"},
            headers={"X-API-Key": "secretkey123456"},
        )
        assert response3.status_code == 429
        assert response3.json()["detail"] == "rate limit exceeded"

    def test_rate_limit_includes_retry_after(self, client_with_rate_limit):
        """El error de rate limit incluye Retry-After."""
        # Hacer 2 requests
        for _ in range(2):
            client_with_rate_limit.post(
                "/ask",
                json={"question": "test"},
                headers={"X-API-Key": "secretkey123456"},
            )

        # El tercer request debe tener Retry-After
        response = client_with_rate_limit.post(
            "/ask",
            json={"question": "test"},
            headers={"X-API-Key": "secretkey123456"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert int(response.headers["Retry-After"]) > 0

    def test_metrics_endpoint_rate_limit_separate(self, client_with_rate_limit):
        """Rate limit se aplica a /metrics también."""
        # 2 requests a /ask
        for _ in range(2):
            client_with_rate_limit.post(
                "/ask",
                json={"question": "test"},
                headers={"X-API-Key": "secretkey123456"},
            )

        # /metrics debe estar limitado también
        response = client_with_rate_limit.get(
            "/metrics",
            headers={"X-API-Key": "secretkey123456"},
        )
        assert response.status_code == 429


class TestMultipleClientsRateLimit:
    """Pruebas de rate limiting con múltiples clientes."""

    @pytest.fixture
    def client_multi_auth(self):
        """Cliente con múltiples clientes autenticados."""
        env = {
            "MODEL_PROVIDER": "fake",
            "API_KEYS": "alice:secretkey123456,bob:anothersecret789",
            "RATE_LIMIT_PER_MINUTE": "2",
        }
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **env}
        settings = load_settings(variables)
        directory = EmployeeDirectory.from_file(EMPLOYEES_PATH)
        app = create_app(settings=settings, directory=directory)
        return TestClient(app)

    def test_rate_limits_separate_per_client(self, client_multi_auth):
        """Cada cliente tiene su propio límite."""
        # alice hace 2 requests
        for _ in range(2):
            response = client_multi_auth.post(
                "/ask",
                json={"question": "test"},
                headers={"X-API-Key": "secretkey123456"},
            )
            assert response.status_code == 200

        # bob también puede hacer 2 (límite separado)
        for _ in range(2):
            response = client_multi_auth.post(
                "/ask",
                json={"question": "test"},
                headers={"X-API-Key": "anothersecret789"},
            )
            assert response.status_code == 200

        # Ambos están ahora en el límite
        alice_response = client_multi_auth.post(
            "/ask",
            json={"question": "test"},
            headers={"X-API-Key": "secretkey123456"},
        )
        assert alice_response.status_code == 429

        bob_response = client_multi_auth.post(
            "/ask",
            json={"question": "test"},
            headers={"X-API-Key": "anothersecret789"},
        )
        assert bob_response.status_code == 429


class TestClientNameInResponse:
    """Pruebas que el nombre del cliente se propaga correctamente."""

    @pytest.fixture
    def client_with_logging(self):
        """Cliente con logging en memoria."""
        env = {
            "MODEL_PROVIDER": "fake",
            "API_KEYS": "alice:secretkey123456",
        }
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **env}
        settings = load_settings(variables)
        directory = EmployeeDirectory.from_file(EMPLOYEES_PATH)
        log_stream = io.StringIO()
        app = create_app(
            settings=settings,
            directory=directory,
            log_stream=log_stream,
        )
        return TestClient(app), log_stream

    def test_client_name_is_in_agent_run_and_audit_log_lines(
        self, client_with_logging
    ):
        """El log lleva el cliente en ``agent_run`` y en ``audit``."""
        client, log_stream = client_with_logging

        response = client.post(
            "/ask",
            json={"question": "¿Quién es EMP-0004?"},
            headers={"X-API-Key": "secretkey123456"},
        )

        assert response.status_code == 200
        lines = [json.loads(row) for row in log_stream.getvalue().splitlines()]
        for event in ("agent_run", "audit"):
            event_lines = [line for line in lines if line["event"] == event]
            assert event_lines, f"no {event} line in the log"
            assert all(line.get("client") == "alice" for line in event_lines)

    def test_api_key_never_appears_in_the_log(self, client_with_logging):
        """La clave no se escribe en el log, con peticiones buenas o malas."""
        client, log_stream = client_with_logging

        client.post(
            "/ask",
            json={"question": "¿Quién es EMP-0004?"},
            headers={"X-API-Key": "secretkey123456"},
        )
        client.post(
            "/ask",
            json={"question": "test"},
            headers={"X-API-Key": "wrong-key-value-xyz"},
        )

        log_content = log_stream.getvalue()
        assert log_content
        assert "secretkey123456" not in log_content
        assert "wrong-key-value-xyz" not in log_content


class TestAuthenticationErrorMessages:
    """Pruebas de mensajes de error de autenticación."""

    @pytest.fixture
    def client_with_auth(self):
        """Cliente con autenticación."""
        env = {
            "MODEL_PROVIDER": "fake",
            "API_KEYS": "alice:secretkey123456",
        }
        variables = {"EMPLOYEES_PATH": str(EMPLOYEES_PATH), **env}
        settings = load_settings(variables)
        directory = EmployeeDirectory.from_file(EMPLOYEES_PATH)
        app = create_app(settings=settings, directory=directory)
        return TestClient(app)

    def test_error_message_does_not_expose_key(self, client_with_auth):
        """El mensaje de error nunca expone la clave."""
        response = client_with_auth.post(
            "/ask",
            json={"question": "test"},
            headers={"X-API-Key": "secretkey123456extra"},
        )
        assert response.status_code == 401
        error_detail = response.json()["detail"]
        assert "secretkey123456extra" not in error_detail
        assert "secretkey123456" not in error_detail

    def test_missing_header_error_message(self, client_with_auth):
        """Mensaje de error consistente sin encabezado."""
        response = client_with_auth.post(
            "/ask",
            json={"question": "test"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid or missing API key"
