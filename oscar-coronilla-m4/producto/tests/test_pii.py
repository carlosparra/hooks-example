"""Pruebas de ``app.pii``: detector local de PII que solo devuelve tipos.

Contrato: ``detect(text)`` devuelve una tupla de tipos únicos en el orden fijo
``email, phone, curp, rfc, card, clabe``; ``mask(text)`` devuelve un objeto con
``text`` (cada dato reemplazado por ``[EMAIL]``, ``[PHONE]``, etc.) y ``types``;
``luhn_ok(digits)`` dice si una cadena de dígitos pasa el algoritmo de Luhn.
"""

from app.pii import detect, luhn_ok, mask

VALID_CARD = "4111111111111111"
CARD_FAILING_LUHN = "4111111111111112"
CLABE_PASSING_LUHN = "002010077777777774"
CURP = "LOPA900101MDFPRN09"


def test_every_kind_of_personal_data_is_detected_by_its_type():
    samples = [
        ("Mi correo es ana.lopez@empresa.com", "email"),
        ("Llama al 442 123 4567", "phone"),
        ("Llama al +52 442-123-4567", "phone"),
        ("Llama al 4421234567", "phone"),
        (f"Mi CURP es {CURP}", "curp"),
        ("RFC de persona física LOPA900101AB1", "rfc"),
        ("RFC de persona moral ABC010203XY9", "rfc"),
        (f"Tarjeta {VALID_CARD}", "card"),
        (f"CLABE {CLABE_PASSING_LUHN}", "clabe"),
    ]

    for text, kind in samples:
        assert detect(text) == (kind,), text


def test_several_types_come_in_a_fixed_order_and_without_values():
    found = detect("Tel 4421234567, correo ana@empresa.com, CLABE 002010077777777774")

    assert found == ("email", "phone", "clabe")
    assert "ana@empresa.com" not in repr(found)


def test_employee_numbers_dates_amounts_and_request_ids_are_not_personal_data():
    texts = [
        "¿Quién es EMP-0004?",
        "Entró el 2019-03-04",
        "Gana $25,000.00 al mes",
        "request_id 7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "Extensión 1234",
    ]

    for text in texts:
        assert not detect(text), text


def test_a_number_that_fails_luhn_is_not_a_card():
    assert luhn_ok(VALID_CARD)
    assert not luhn_ok(CARD_FAILING_LUHN)
    assert not detect(f"Tarjeta {CARD_FAILING_LUHN}")


def test_eighteen_digits_are_a_clabe_even_if_they_pass_luhn():
    assert luhn_ok(CLABE_PASSING_LUHN)
    assert detect(CLABE_PASSING_LUHN) == ("clabe",)


def test_an_rfc_inside_a_curp_is_counted_only_as_curp():
    assert detect(CURP) == ("curp",)


def test_mask_replaces_every_value_and_lists_each_type_once():
    result = mask("Correo ana@empresa.com, tel 442 123 4567, otra vez ana@empresa.com")

    assert result.text == "Correo [EMAIL], tel [PHONE], otra vez [EMAIL]"
    assert tuple(result.types) == ("email", "phone")
    clean = mask("Jorge Díaz es Líder técnico (EMP-0004).")
    assert clean.text == "Jorge Díaz es Líder técnico (EMP-0004)."
    assert not tuple(clean.types)
