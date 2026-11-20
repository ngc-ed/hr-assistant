"""Pruebas unitarias del enmascarado de datos personales (punto 1 del reto).

Contrato esperado: ``mask_pii(text)`` devuelve ``(texto_enmascarado, conteos)``
donde ``conteos`` es ``{"CORREO": 2, ...}``. Nunca devuelve los valores.
"""

from app.pii import mask_pii

SAMPLES = {
    "CORREO": "sofia.gomez@example.com",
    "TELEFONO": "5512345678",
    "RFC": "GOMS800101AB1",
    "CURP": "GOMS800101HDFMRN09",
    "NSS": "12345678901",
    "TARJETA": "4111111111111111",
}


def test_each_kind_of_personal_data_is_replaced_by_its_tag():
    for kind, value in SAMPLES.items():
        masked, counts = mask_pii(f"dato {value} fin")
        assert masked == f"dato [{kind}] fin", kind
        assert counts == {kind: 1}, kind


def test_several_kinds_in_one_text_are_counted_and_none_survives():
    text = "Escribe a ana@example.com o a luis@example.com, tel 5512345678"
    masked, counts = mask_pii(text)
    assert counts == {"CORREO": 2, "TELEFONO": 1}
    assert "@" not in masked and "5512345678" not in masked


def test_employee_ids_and_dates_are_not_mistaken_for_personal_data():
    text = "EMP-0001 y EMP-0004 empezaron el 2019-03-04 en Tecnología"
    masked, counts = mask_pii(text)
    assert masked == text
    assert not counts
