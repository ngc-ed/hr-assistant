"""Pruebas unitarias de las métricas de negocio de ``/metrics`` (punto 6)."""

import dataclasses

from app.llm import FakeModel

API_KEY = "clave-de-prueba-0123456789"
AUTH = {"X-API-Key": API_KEY}
ENV = {"API_KEYS": f"tester:{API_KEY}"}


class CachedModel:
    """Marca cada respuesta del modelo interno como servida desde la caché.

    :param inner: Modelo al que se delega la respuesta
    :type inner: object
    """

    def __init__(self, inner):
        self.inner = inner

    def complete(self, messages):
        """Delega y marca la respuesta como cacheada.

        :param messages: Conversación que recibe el modelo
        :type messages: list[dict]
        :return: La respuesta con ``cached=True``
        :rtype: Completion
        """
        return dataclasses.replace(self.inner.complete(messages), cached=True)


def _ask(client, question):
    response = client.post("/ask", json={"question": question}, headers=AUTH)
    assert response.status_code == 200
    return response


def _metrics(client):
    return client.get("/metrics", headers=AUTH).json()


def test_questions_and_tool_usage_are_counted_by_name(make_client):
    client = make_client(env=ENV)
    _ask(client, "Lista el departamento de Ventas")
    _ask(client, "Lista el departamento de Ventas")
    _ask(client, "¿Quién es EMP-0001?")
    metrics = _metrics(client)
    assert metrics["questions_by_department"]["Ventas"] == 2
    assert metrics["tool_usage"] == {"search_by_department": 2, "get_employee": 1}


def test_cache_hit_pct_goes_from_zero_to_one_hundred(make_client, directory):
    plain = make_client(env=ENV)
    _ask(plain, "¿Quién es EMP-0001?")
    cached = make_client(env=ENV, model=CachedModel(FakeModel(directory.departments())))
    _ask(cached, "¿Quién es EMP-0001?")
    assert _metrics(plain)["cache_hit_pct"] == 0
    assert _metrics(cached)["cache_hit_pct"] == 100


def test_pii_by_type_counts_each_detection(make_client):
    client = make_client(env=ENV)
    _ask(client, "Mi correo es a@example.com")
    _ask(client, "Otro correo b@example.com y mi RFC GOMS800101AB1")
    assert _metrics(client)["pii_by_type"] == {"CORREO": 2, "RFC": 1}
