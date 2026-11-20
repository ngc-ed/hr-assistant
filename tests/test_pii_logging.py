"""Pruebas unitarias: los valores personales nunca llegan al log (punto 1)."""

import io

from app.gateway import ModelUnavailableError

EMAIL = "sofia.gomez@example.com"
RFC = "GOMS800101AB1"
QUESTION = f"Mi correo es {EMAIL} y mi RFC es {RFC}"


class UnavailableModel:
    """Modelo que falla como si el gateway no respondiera."""

    def complete(self, messages):
        """Lanza el error del gateway.

        :param messages: Conversación que recibe el modelo
        :type messages: list[dict]
        :raises ModelUnavailableError: Siempre
        """
        raise ModelUnavailableError()


def test_a_failing_model_still_leaves_no_personal_value_in_the_log(make_client):
    log = io.StringIO()
    client = make_client(model=UnavailableModel(), log_stream=log)
    response = client.post("/ask", json={"question": QUESTION})
    assert response.status_code == 502
    text = log.getvalue()
    assert EMAIL not in text and RFC not in text
    assert EMAIL not in response.text and RFC not in response.text
