"""Pruebas unitarias de la página del tablero (punto 5 del reto)."""

API_KEY = "clave-de-prueba-0123456789"
ENV = {"API_KEYS": f"tester:{API_KEY}"}


def test_the_page_reads_the_key_from_session_storage_and_polls_metrics(make_client):
    page = make_client(env=ENV).get("/dashboard").text
    assert "sessionStorage" in page
    assert "X-API-Key" in page
    assert "/metrics" in page
    assert "5000" in page, "debe leer /metrics cada 5 segundos"
    for label in ("error_rate", "p50", "p95", "pii_by_type", "cache_hit_pct"):
        assert label in page, label
