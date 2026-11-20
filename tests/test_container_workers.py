"""Pruebas de la concurrencia del contenedor (punto 4 del reto)."""

from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parent.parent


def test_container_and_render_use_web_concurrency_with_two_workers_by_default():
    dockerfile = (PRODUCT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    render = (PRODUCT_ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "--workers ${WEB_CONCURRENCY:-2}" in dockerfile
    assert "WEB_CONCURRENCY" in render
