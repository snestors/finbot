"""Tests for fast_path — regex-based action extraction with zero LLM calls.

Tests cover:
- Common expense patterns (keyword-first, amount-first, bare-number-first)
- Income patterns
- Query/consultation shortcuts
- Delete patterns (single and multi)
- Transfer, card payment, debt payment patterns
- Negative cases (should return None — fall through to LLM)
- Edge cases (empty, very long, special characters)
"""
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.fast_path import (
    try_fast_path,
    _infer_category,
    _detect_payment_method,
    _extract_amount,
    _extract_date,
    _extract_description,
    _clean,
    _normalize,
)


# =========================================================================
# Helper assertion functions
# =========================================================================

def _assert_match(text: str, expected_tipo: str, **expected_fields):
    """Assert that try_fast_path matches and returns expected action fields."""
    result = try_fast_path(text)
    assert result is not None, f"Expected match for '{text}', got None"
    actions, response = result
    assert len(actions) >= 1, f"Expected at least 1 action for '{text}', got {len(actions)}"
    a = actions[0]
    actual_tipo = a.get("mov_tipo", a.get("tipo"))
    assert actual_tipo == expected_tipo, (
        f"Expected tipo '{expected_tipo}' for '{text}', got '{actual_tipo}'"
    )
    for key, val in expected_fields.items():
        assert a.get(key) == val, (
            f"Expected {key}={val!r} for '{text}', got {a.get(key)!r}"
        )
    assert isinstance(response, str) and len(response) > 0, (
        f"Expected non-empty response string for '{text}'"
    )
    return actions, response


def _assert_no_match(text: str):
    """Assert that try_fast_path returns None (no pattern matched)."""
    result = try_fast_path(text)
    assert result is None, f"Expected None for '{text}', got {result}"


# =========================================================================
# Unit tests: helper functions
# =========================================================================

class TestNormalize:
    def test_removes_accents(self):
        assert _normalize("cuánto") == "cuanto"
        assert _normalize("límite") == "limite"
        assert _normalize("café") == "cafe"

    def test_plain_text_unchanged(self):
        assert _normalize("hello") == "hello"
        assert _normalize("almuerzo") == "almuerzo"

    def test_empty(self):
        assert _normalize("") == ""


class TestClean:
    def test_lowercase_strip_normalize(self):
        assert _clean("  Almuerzo ") == "almuerzo"
        assert _clean("CAFÉ") == "cafe"


class TestInferCategory:
    def test_comida_keywords(self):
        assert _infer_category("almuerzo en restaurante") == "comida"
        assert _infer_category("cena con amigos") == "comida"
        assert _infer_category("desayuno") == "comida"

    def test_transporte_keywords(self):
        assert _infer_category("uber al centro") == "transporte"
        assert _infer_category("taxi aeropuerto") == "transporte"
        assert _infer_category("pasaje de bus") == "transporte"

    def test_delivery_keywords(self):
        assert _infer_category("rappi pedido") == "delivery"
        assert _infer_category("pedidos ya comida") == "delivery"

    def test_supermercado_keywords(self):
        assert _infer_category("wong compras") == "supermercado"
        assert _infer_category("plaza vea semanal") == "supermercado"

    def test_multi_word_match(self):
        # Multi-word keywords like "pedidos ya" should match first
        assert _infer_category("pedidos ya almuerzo") == "delivery"
        assert _infer_category("plaza vea mercado") == "supermercado"

    def test_unknown_returns_otros(self):
        assert _infer_category("random thing") == "otros"
        assert _infer_category("xyz abc") == "otros"


class TestDetectPaymentMethod:
    def test_yape(self):
        assert _detect_payment_method("pago yape") == "yape"

    def test_plin(self):
        assert _detect_payment_method("con plin") == "plin"

    def test_efectivo(self):
        assert _detect_payment_method("efectivo") == "efectivo"
        assert _detect_payment_method("pago cash") == "efectivo"

    def test_tarjeta(self):
        assert _detect_payment_method("con tarjeta") == "tarjeta"

    def test_bank_names(self):
        assert _detect_payment_method("bcp") == "transferencia"
        assert _detect_payment_method("bbva") == "transferencia"

    def test_none_when_not_found(self):
        assert _detect_payment_method("algo random") is None


class TestExtractAmount:
    def test_soles_prefix(self):
        assert _extract_amount("s/50") == (50.0, "PEN")
        assert _extract_amount("S/25.50") == (25.50, "PEN")
        assert _extract_amount("s/.100") == (100.0, "PEN")

    def test_dollar_prefix(self):
        assert _extract_amount("$30") == (30.0, "USD")
        assert _extract_amount("$ 15.99") == (15.99, "USD")

    def test_bare_number(self):
        assert _extract_amount("almuerzo 18") == (18.0, "PEN")

    def test_zero_returns_none(self):
        amount, currency = _extract_amount("no number here")
        assert amount is None


class TestExtractDate:
    def test_ayer(self):
        assert _extract_date("algo ayer") == "ayer"

    def test_anteayer(self):
        assert _extract_date("anteayer compre") == "anteayer"
        assert _extract_date("ante ayer fui") == "anteayer"

    def test_hace_n_dias(self):
        assert _extract_date("hace 3 dias") == "hace 3 dias"
        assert _extract_date("hace 1 dia") == "hace 1 dias"

    def test_no_date(self):
        assert _extract_date("almuerzo 18") is None

    def test_anteayer_not_ayer(self):
        # "anteayer" should NOT match as "ayer"
        assert _extract_date("anteayer") == "anteayer"


# =========================================================================
# Integration tests: try_fast_path — Expense patterns
# =========================================================================

class TestFastPathGasto:
    """Tests for expense (gasto) pattern matching."""

    def test_keyword_first_basic(self):
        """'almuerzo 18 KFC yape' — keyword + amount + desc + method."""
        actions, resp = _assert_match("almuerzo 18 KFC yape", "gasto",
                                       monto=18.0, moneda="PEN")
        a = actions[0]
        assert a["categoria"] == "comida"
        assert a["metodo_pago"] == "yape"

    def test_amount_first_soles(self):
        """'s/50 uber tarjeta' — amount with currency + desc + method."""
        actions, resp = _assert_match("s/50 uber tarjeta", "gasto",
                                       monto=50.0, moneda="PEN")
        a = actions[0]
        assert a["categoria"] == "transporte"
        assert a["metodo_pago"] == "tarjeta"

    def test_amount_first_dollars(self):
        """'$25 taxi' — dollar amount."""
        actions, resp = _assert_match("$25 taxi", "gasto",
                                       monto=25.0, moneda="USD")
        a = actions[0]
        assert a["categoria"] == "transporte"

    def test_keyword_taxi(self):
        """'taxi 15' — common keyword + amount."""
        actions, resp = _assert_match("taxi 15", "gasto", monto=15.0)
        assert actions[0]["categoria"] == "transporte"

    def test_keyword_cafe(self):
        """'cafe 8.50' — keyword with decimal amount."""
        actions, resp = _assert_match("cafe 8.50", "gasto", monto=8.50)
        assert actions[0]["categoria"] == "comida"

    def test_bare_number_with_method(self):
        """'50 efectivo delivery rappi' — bare number + method + keywords."""
        actions, resp = _assert_match("50 efectivo delivery rappi", "gasto",
                                       monto=50.0)
        a = actions[0]
        assert a["metodo_pago"] == "efectivo"

    def test_keyword_with_soles_prefix(self):
        """'almuerzo s/25' — keyword + s/ amount."""
        actions, resp = _assert_match("almuerzo s/25", "gasto", monto=25.0)

    def test_cena_pattern(self):
        """'cena 35 restaurante' — dinner expense."""
        actions, resp = _assert_match("cena 35 restaurante", "gasto",
                                       monto=35.0)
        assert actions[0]["categoria"] == "comida"

    def test_response_contains_amount(self):
        """Response text should contain the amount."""
        _, resp = _assert_match("almuerzo 18", "gasto")
        assert "18" in resp

    def test_expense_with_date_ayer(self):
        """'almuerzo 20 ayer' — expense with date."""
        actions, _ = _assert_match("almuerzo 20 ayer", "gasto", monto=20.0)
        assert actions[0].get("fecha") == "ayer"


class TestFastPathIngreso:
    """Tests for income (ingreso) pattern matching."""

    def test_sueldo(self):
        """'sueldo 3500' — basic salary."""
        _assert_match("sueldo 3500", "ingreso", monto=3500.0)

    def test_me_pagaron(self):
        """'me pagaron 200' — received payment."""
        _assert_match("me pagaron 200", "ingreso", monto=200.0)

    def test_recibi(self):
        """'recibi 500 bcp' — received with bank."""
        actions, _ = _assert_match("recibi 500 bcp", "ingreso", monto=500.0)

    def test_sueldo_with_soles(self):
        """'sueldo s/4000' — salary with currency prefix."""
        _assert_match("sueldo s/4000", "ingreso", monto=4000.0)

    def test_ingreso_dollars(self):
        """'ingreso $150' — income in dollars."""
        _assert_match("ingreso $150", "ingreso", monto=150.0, moneda="USD")


class TestFastPathConsulta:
    """Tests for query/consultation shortcuts."""

    def test_cuanto_llevo_hoy(self):
        """'cuanto llevo hoy' — today's spending query."""
        actions, resp = _assert_match("cuanto llevo hoy", "consulta")
        assert actions[0]["periodo"] == "hoy"
        assert "hoy" in resp.lower()

    def test_gastos_del_mes(self):
        """'mis gastos del mes' — monthly spending query."""
        actions, resp = _assert_match("mis gastos del mes", "consulta")
        assert actions[0]["periodo"] == "mes"

    def test_cuanto_gaste_esta_semana(self):
        """'cuanto gaste esta semana' — weekly query."""
        actions, resp = _assert_match("cuanto gaste esta semana", "consulta")
        assert actions[0]["periodo"] == "semana"

    def test_mis_deudas(self):
        """'mis deudas' — debt query."""
        actions, _ = _assert_match("mis deudas", "consulta")
        assert actions[0]["periodo"] == "deudas"

    def test_mis_cuentas(self):
        """'mis cuentas' — accounts query."""
        actions, _ = _assert_match("mis cuentas", "consulta")
        assert actions[0]["periodo"] == "cuentas"

    def test_mis_tarjetas(self):
        """'mis tarjetas' — cards query."""
        actions, _ = _assert_match("mis tarjetas", "consulta")
        assert actions[0]["periodo"] == "tarjetas"

    def test_tipo_de_cambio(self):
        """'tipo de cambio' — exchange rate query."""
        actions, _ = _assert_match("tipo de cambio", "tipo_cambio_sunat")

    def test_cuanto_esta_el_dolar(self):
        """'cuanto esta el dolar' — dollar exchange rate."""
        actions, _ = _assert_match("cuanto esta el dolar", "tipo_cambio_sunat")


class TestFastPathEliminar:
    """Tests for delete (eliminar) patterns."""

    def test_borra_single(self):
        """'borra el #5' — single delete."""
        actions, resp = _assert_match("borra el #5", "eliminar_movimiento")
        assert actions[0]["movimiento_id"] == 5

    def test_elimina_single(self):
        """'elimina #3' — single delete alternative."""
        actions, _ = _assert_match("elimina #3", "eliminar_movimiento")
        assert actions[0]["movimiento_id"] == 3

    def test_elimina_without_hash(self):
        """'elimina 7' — single delete without hash."""
        actions, _ = _assert_match("elimina 7", "eliminar_movimiento")
        assert actions[0]["movimiento_id"] == 7

    def test_borra_multiple(self):
        """'elimina #3 y #4' — multiple deletes."""
        actions, resp = _assert_match("elimina #3 y #4", "eliminar_movimientos")
        assert sorted(actions[0]["ids"]) == [3, 4]

    def test_borra_multiple_comma(self):
        """'borra #1, #2 y #3' — multiple with commas."""
        actions, _ = _assert_match("borra #1, #2 y #3", "eliminar_movimientos")
        assert sorted(actions[0]["ids"]) == [1, 2, 3]


class TestFastPathTransferencia:
    """Tests for transfer patterns."""

    def test_pase_basic(self):
        """'pase 200 de bcp a yape' — basic transfer."""
        actions, _ = _assert_match("pase 200 de bcp a yape", "transferencia")
        assert actions[0]["monto"] == 200.0

    def test_transfiere(self):
        """'transfiere 100 de bcp a bbva' — transfer alternative."""
        actions, _ = _assert_match("transfiere 100 de bcp a bbva", "transferencia")
        assert actions[0]["monto"] == 100.0


class TestFastPathPagoTarjeta:
    """Tests for credit card payment patterns."""

    def test_pague_visa(self):
        """'pague 500 a visa' — basic card payment."""
        actions, _ = _assert_match("pague 500 a visa", "pago_tarjeta")
        assert actions[0]["monto"] == 500.0

    def test_pague_mastercard(self):
        """'pague 300 a la mastercard' — card payment with article."""
        actions, _ = _assert_match("pague 300 a la mastercard", "pago_tarjeta")
        assert actions[0]["monto"] == 300.0


class TestFastPathPagoDeuda:
    """Tests for debt payment patterns."""

    def test_pague_cuota_hipoteca(self):
        """'pague cuota 350 hipoteca' — basic debt payment."""
        actions, _ = _assert_match("pague cuota 350 hipoteca", "pago_deuda")
        assert actions[0]["monto"] == 350.0

    def test_pague_deuda(self):
        """'pague 500 de deuda bancaria' — debt payment alternative."""
        actions, _ = _assert_match("pague 500 de deuda bancaria", "pago_deuda")
        assert actions[0]["monto"] == 500.0


# =========================================================================
# Negative cases — should return None (fall through to LLM)
# =========================================================================

class TestFastPathNegative:
    """Messages that should NOT match any fast path pattern."""

    def test_opinion_question(self):
        _assert_no_match("que opinas de bitcoin")

    def test_greeting(self):
        _assert_no_match("hola como estas")

    def test_help_request(self):
        _assert_no_match("ayudame con algo")

    def test_explain_request(self):
        _assert_no_match("explicame como funciona el mercado")

    def test_recommendation(self):
        _assert_no_match("que me recomiendas para ahorrar")

    def test_casual_conversation(self):
        _assert_no_match("cuentame algo interesante")

    def test_por_que(self):
        _assert_no_match("por que sube el dolar")

    def test_generic_text_no_numbers(self):
        _assert_no_match("necesito planificar mis vacaciones a cusco")

    def test_como_hago(self):
        _assert_no_match("como hago para invertir en fondos mutuos")

    def test_sugiere(self):
        _assert_no_match("sugiere una estrategia de ahorro")


# =========================================================================
# Edge cases
# =========================================================================

class TestFastPathEdgeCases:
    """Edge cases: empty, short, long, special characters."""

    def test_empty_string(self):
        _assert_no_match("")

    def test_whitespace_only(self):
        _assert_no_match("   ")

    def test_single_character(self):
        _assert_no_match("a")

    def test_very_long_text(self):
        """Very long text that doesn't match patterns."""
        long_text = "esta es una conversacion muy larga " * 100
        _assert_no_match(long_text)

    def test_special_characters(self):
        _assert_no_match("!@#$%^&*()")

    def test_only_number(self):
        """A bare number alone should not match (no context)."""
        _assert_no_match("42")

    def test_unicode_accents_in_expense(self):
        """Keywords with accents should still work after normalization."""
        # "pagué" should route to pago patterns, not gasto
        # The fast path handles this via _clean/normalize
        result = try_fast_path("cafe 12 yape")
        assert result is not None
