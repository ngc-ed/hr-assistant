"""Pruebas unitarias para rate limiting por cliente y minuto."""

import pytest
from fastapi import HTTPException

from app.rate_limiter import RateLimiter


class MockClock:
    """Reloj simulado para pruebas de rate limiting."""

    def __init__(self, start_time=0.0):
        self._current_time = start_time

    def monotonic(self):
        """Devuelve el tiempo actual sin avanzar."""
        return self._current_time

    def advance(self, seconds):
        """Avanza el reloj manual segundos."""
        self._current_time += seconds


class TestRateLimiterBasic:
    """Pruebas básicas del rate limiter."""

    def test_rate_limiter_initialization(self):
        """Inicializar un rate limiter."""
        limiter = RateLimiter(requests_per_minute=10)
        assert limiter.requests_per_minute == 10

    def test_rate_limiter_with_custom_clock(self):
        """Inicializar rate limiter con reloj personalizado."""
        clock = MockClock(start_time=100.0)
        limiter = RateLimiter(requests_per_minute=5, clock=clock)
        assert limiter.clock == clock

    def test_rate_limiter_allows_first_request(self):
        """El primer request de un cliente pasa."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=3, clock=clock)

        # No debe lanzar excepción
        limiter.check_rate_limit("alice")

    def test_rate_limiter_allows_multiple_requests_within_limit(self):
        """Múltiples requests dentro del límite pasan."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=3, clock=clock)

        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")

    def test_rate_limiter_rejects_request_exceeding_limit(self):
        """Un request que excede el límite es rechazado."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=3, clock=clock)

        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")

        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit("alice")

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail == "rate limit exceeded"

    def test_rate_limiter_response_includes_retry_after(self):
        """El error de rate limit incluye encabezado Retry-After."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=2, clock=clock)

        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")

        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit("alice")

        assert "Retry-After" in exc_info.value.headers
        retry_after = int(exc_info.value.headers["Retry-After"])
        assert retry_after > 0
        assert retry_after <= 60

    def test_rate_limiter_separate_limits_per_client(self):
        """Cada cliente tiene su propio límite."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=2, clock=clock)

        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")

        # bob no ha hecho requests, así que puede hacer 2
        limiter.check_rate_limit("bob")
        limiter.check_rate_limit("bob")

        # alice está en el límite, bob también
        with pytest.raises(HTTPException):
            limiter.check_rate_limit("alice")

        with pytest.raises(HTTPException):
            limiter.check_rate_limit("bob")

    def test_rate_limiter_reset_after_minute(self):
        """El límite se resetea después de 60 segundos."""
        clock = MockClock(start_time=0.0)
        limiter = RateLimiter(requests_per_minute=2, clock=clock)

        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")

        # alice está en el límite
        with pytest.raises(HTTPException):
            limiter.check_rate_limit("alice")

        # Avanzar 60 segundos
        clock.advance(60.0)

        # Ahora alice puede hacer más requests
        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")

    def test_rate_limiter_sliding_window(self):
        """El rate limiter usa ventana móvil de 60 segundos."""
        clock = MockClock(start_time=0.0)
        limiter = RateLimiter(requests_per_minute=3, clock=clock)

        # Hacer 3 requests en el segundo 0
        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("alice")

        # En el segundo 30, el primer request sigue dentro de 60 segundos
        clock.advance(30.0)
        with pytest.raises(HTTPException):
            limiter.check_rate_limit("alice")

        # En el segundo 61, el primer request está fuera de 60 segundos
        clock.advance(31.0)
        limiter.check_rate_limit("alice")


class TestRateLimiterEdgeCases:
    """Pruebas de casos borde del rate limiter."""

    def test_rate_limiter_zero_limit(self):
        """Rate limiter con límite 0 rechaza todo."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=0, clock=clock)

        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit("alice")

        assert exc_info.value.status_code == 429

    def test_rate_limiter_large_limit(self):
        """Rate limiter con límite grande."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=1000, clock=clock)

        for _ in range(500):
            limiter.check_rate_limit("alice")

    def test_rate_limiter_many_clients(self):
        """Rate limiter con muchos clientes independientes."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=2, clock=clock)

        clients = [f"client_{i}" for i in range(100)]

        # Cada cliente hace 2 requests
        for client in clients:
            limiter.check_rate_limit(client)
            limiter.check_rate_limit(client)

        # El 3er request de cualquier cliente falla
        for client in clients:
            with pytest.raises(HTTPException):
                limiter.check_rate_limit(client)

    def test_rate_limiter_retry_after_accuracy(self):
        """El encabezado Retry-After es preciso."""
        clock = MockClock(start_time=0.0)
        limiter = RateLimiter(requests_per_minute=1, clock=clock)

        limiter.check_rate_limit("alice")

        # En el segundo 30
        clock.advance(30.0)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit("alice")

        retry_after = int(exc_info.value.headers["Retry-After"])
        assert retry_after == 30  # 60 - 30 = 30

    def test_rate_limiter_empty_client_name(self):
        """Rate limiter maneja clientes con nombre vacío."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=2, clock=clock)

        limiter.check_rate_limit("")
        limiter.check_rate_limit("")

        with pytest.raises(HTTPException):
            limiter.check_rate_limit("")

    def test_rate_limiter_special_client_names(self):
        """Rate limiter maneja clientes con nombres especiales."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=1, clock=clock)

        special_clients = [
            "client-with-dash",
            "client_with_underscore",
            "client.with.dot",
            "UPPERCASE",
        ]

        for client in special_clients:
            limiter.check_rate_limit(client)
            with pytest.raises(HTTPException):
                limiter.check_rate_limit(client)


class TestRateLimiterIntegration:
    """Pruebas de integración del rate limiter."""

    def test_rate_limiter_realistic_scenario(self):
        """Escenario realista: 30 requests por minuto."""
        clock = MockClock(start_time=0.0)
        limiter = RateLimiter(requests_per_minute=30, clock=clock)

        # alice hace 30 requests rápidamente (todos dentro del minuto)
        for _ in range(30):
            limiter.check_rate_limit("alice")

        # El siguiente falla
        with pytest.raises(HTTPException):
            limiter.check_rate_limit("alice")

    def test_rate_limiter_burst_handling(self):
        """Rate limiter maneja ráfagas de requests."""
        clock = MockClock(start_time=0.0)
        limiter = RateLimiter(requests_per_minute=10, clock=clock)

        # Ráfaga de 10 requests
        for _ in range(10):
            limiter.check_rate_limit("alice")

        # El siguiente falla
        with pytest.raises(HTTPException):
            limiter.check_rate_limit("alice")

        # Esperar a que el primer request salga de la ventana
        clock.advance(60.0)

        # Ahora puede hacer el siguiente
        limiter.check_rate_limit("alice")

    def test_rate_limiter_multiple_clients_mixed(self):
        """Múltiples clientes con límite diferente."""
        clock = MockClock()
        limiter = RateLimiter(requests_per_minute=3, clock=clock)

        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("bob")
        limiter.check_rate_limit("alice")
        limiter.check_rate_limit("charlie")
        limiter.check_rate_limit("bob")
        limiter.check_rate_limit("alice")

        # alice ha alcanzado 3, falla
        with pytest.raises(HTTPException):
            limiter.check_rate_limit("alice")

        # bob puede hacer uno más (2 totales)
        limiter.check_rate_limit("bob")

        # charlie puede hacer dos más (1 total hasta ahora)
        limiter.check_rate_limit("charlie")
        limiter.check_rate_limit("charlie")
