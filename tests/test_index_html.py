"""Prueba de seguridad de la página web."""

from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "app" / "static" / "index.html"


def test_page_paints_answers_with_text_content_never_inner_html():
    page = INDEX.read_text(encoding="utf-8")
    assert "textContent" in page
    assert "innerHTML" not in page
