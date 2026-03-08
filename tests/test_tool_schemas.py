"""Tests for tool_schemas — tool_call_to_action converter.

Tests cover:
- Each tool name maps to correct action type
- Required fields are preserved
- Optional fields have defaults
- MCP tools get proper wrapper format
- Unknown tools fall through gracefully
"""
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.tool_schemas import (
    tool_call_to_action,
    TOOLS,
    _MCP_TOOLS,
    _MOV_TYPE_MAP,
    _DIRECT_TOOLS,
    _GOOGLE_EMAIL,
)


# =========================================================================
# Movement registration tools -> movimiento action
# =========================================================================

class TestMovementTools:
    """registrar_* tools should map to movimiento action with correct mov_tipo."""

    def test_registrar_gasto(self):
        action = tool_call_to_action("registrar_gasto", {
            "monto": 25.0,
            "descripcion": "almuerzo",
            "categoria": "comida",
            "metodo_pago": "yape",
        })
        assert action["tipo"] == "movimiento"
        assert action["mov_tipo"] == "gasto"
        assert action["monto"] == 25.0
        assert action["descripcion"] == "almuerzo"
        assert action["categoria"] == "comida"
        assert action["metodo_pago"] == "yape"

    def test_registrar_ingreso(self):
        action = tool_call_to_action("registrar_ingreso", {
            "monto": 3500,
            "descripcion": "sueldo",
        })
        assert action["tipo"] == "movimiento"
        assert action["mov_tipo"] == "ingreso"
        assert action["monto"] == 3500

    def test_registrar_transferencia(self):
        action = tool_call_to_action("registrar_transferencia", {
            "monto": 200,
            "cuenta_id": 1,
            "cuenta_destino_id": 2,
        })
        assert action["tipo"] == "movimiento"
        assert action["mov_tipo"] == "transferencia"
        assert action["cuenta_id"] == 1
        assert action["cuenta_destino_id"] == 2

    def test_registrar_pago_tarjeta(self):
        action = tool_call_to_action("registrar_pago_tarjeta", {
            "monto": 500,
            "tarjeta_id": 3,
        })
        assert action["tipo"] == "movimiento"
        assert action["mov_tipo"] == "pago_tarjeta"
        assert action["tarjeta_id"] == 3

    def test_registrar_pago_deuda(self):
        action = tool_call_to_action("registrar_pago_deuda", {
            "monto": 350,
            "nombre": "hipoteca",
        })
        assert action["tipo"] == "movimiento"
        assert action["mov_tipo"] == "pago_deuda"
        assert action["nombre"] == "hipoteca"

    def test_registrar_pago_cobro(self):
        action = tool_call_to_action("registrar_pago_cobro", {
            "monto": 100,
            "nombre": "Pedro",
        })
        assert action["tipo"] == "movimiento"
        assert action["mov_tipo"] == "pago_cobro"
        assert action["nombre"] == "Pedro"

    def test_all_mov_types_covered(self):
        """Every entry in _MOV_TYPE_MAP should produce a valid movimiento action."""
        for tool_name, mov_tipo in _MOV_TYPE_MAP.items():
            action = tool_call_to_action(tool_name, {"monto": 100})
            assert action["tipo"] == "movimiento"
            assert action["mov_tipo"] == mov_tipo

    def test_optional_fields_preserved(self):
        """Optional fields like fecha, moneda, cuotas should pass through."""
        action = tool_call_to_action("registrar_gasto", {
            "monto": 50,
            "fecha": "ayer",
            "moneda": "USD",
            "cuotas": 3,
            "tarjeta_id": 5,
        })
        assert action["fecha"] == "ayer"
        assert action["moneda"] == "USD"
        assert action["cuotas"] == 3
        assert action["tarjeta_id"] == 5


# =========================================================================
# Consulta tools
# =========================================================================

class TestConsultaTools:
    def test_consultar_resumen(self):
        action = tool_call_to_action("consultar_resumen", {"periodo": "mes"})
        assert action["tipo"] == "consulta"
        assert action["periodo"] == "mes"

    def test_consultar_resumen_default(self):
        action = tool_call_to_action("consultar_resumen", {})
        assert action["tipo"] == "consulta"
        assert action["periodo"] == "hoy"

    def test_consultar_tipo_cambio(self):
        action = tool_call_to_action("consultar_tipo_cambio", {})
        assert action["tipo"] == "tipo_cambio_sunat"

    def test_convertir_moneda(self):
        action = tool_call_to_action("convertir_moneda", {
            "monto": 100,
            "de": "USD",
            "a": "PEN",
        })
        assert action["tipo"] == "consulta_cambio"
        assert action["monto"] == 100
        assert action["de"] == "USD"
        assert action["a"] == "PEN"


# =========================================================================
# Direct passthrough tools
# =========================================================================

class TestDirectTools:
    """Tools in _DIRECT_TOOLS should pass through with tipo = tool_name."""

    def test_eliminar_movimiento(self):
        action = tool_call_to_action("eliminar_movimiento", {"movimiento_id": 5})
        assert action["tipo"] == "eliminar_movimiento"
        assert action["movimiento_id"] == 5

    def test_eliminar_movimientos(self):
        action = tool_call_to_action("eliminar_movimientos", {"ids": [1, 2, 3]})
        assert action["tipo"] == "eliminar_movimientos"
        assert action["ids"] == [1, 2, 3]

    def test_actualizar_movimiento(self):
        action = tool_call_to_action("actualizar_movimiento", {
            "movimiento_id": 7,
            "monto": 30,
            "categoria": "transporte",
        })
        assert action["tipo"] == "actualizar_movimiento"
        assert action["movimiento_id"] == 7
        assert action["monto"] == 30

    def test_set_presupuesto(self):
        action = tool_call_to_action("set_presupuesto", {
            "categoria": "comida",
            "limite": 500,
        })
        assert action["tipo"] == "set_presupuesto"
        assert action["categoria"] == "comida"
        assert action["limite"] == 500

    def test_set_perfil(self):
        action = tool_call_to_action("set_perfil", {"nombre": "Nestor"})
        assert action["tipo"] == "set_perfil"
        assert action["nombre"] == "Nestor"

    def test_memorizar(self):
        action = tool_call_to_action("memorizar", {
            "clave": "cumple",
            "valor": "15 de mayo",
        })
        assert action["tipo"] == "memorizar"
        assert action["clave"] == "cumple"

    def test_smart_home(self):
        action = tool_call_to_action("smart_home", {
            "comando": "enciende la luz del cuarto",
        })
        assert action["tipo"] == "smart_home"
        assert action["comando"] == "enciende la luz del cuarto"

    def test_all_direct_tools_covered(self):
        """Every _DIRECT_TOOLS entry should produce tipo = tool_name,
        EXCEPT tools with special handlers that run first (consultar_consumo -> consulta_consumo).
        """
        # consultar_consumo has a special handler that maps to 'consulta_consumo'
        special_overrides = {"consultar_consumo": "consulta_consumo"}
        for tool_name in _DIRECT_TOOLS:
            action = tool_call_to_action(tool_name, {"dummy": "test"})
            expected_tipo = special_overrides.get(tool_name, tool_name)
            assert action["tipo"] == expected_tipo, (
                f"{tool_name} expected tipo={expected_tipo}, got tipo={action['tipo']}"
            )


# =========================================================================
# Special mapping tools
# =========================================================================

class TestSpecialMappings:
    def test_crear_tarjeta(self):
        action = tool_call_to_action("crear_tarjeta", {
            "nombre": "Visa BCP",
            "banco": "BCP",
        })
        assert action["tipo"] == "tarjeta"
        assert action["nombre"] == "Visa BCP"

    def test_registrar_cobro(self):
        action = tool_call_to_action("registrar_cobro", {
            "deudor": "Pedro",
            "monto": 200,
        })
        assert action["tipo"] == "cobro"
        assert action["deudor"] == "Pedro"

    def test_buscar_gasto(self):
        action = tool_call_to_action("buscar_gasto", {"texto": "uber"})
        assert action["tipo"] == "buscar_gasto"
        assert action["texto"] == "uber"

    def test_consultar_consumo(self):
        action = tool_call_to_action("consultar_consumo", {
            "desde": "2026-03-01",
            "hasta": "2026-03-07",
            "agrupacion": "dia",
        })
        assert action["tipo"] == "consulta_consumo"
        assert action["desde"] == "2026-03-01"


# =========================================================================
# MCP tools — should get wrapped in tool action with google email
# =========================================================================

class TestMCPTools:
    """MCP tools should produce tipo='tool' actions with params dict."""

    def test_create_event(self):
        action = tool_call_to_action("create_event", {
            "summary": "Reunion",
            "start_time": "2026-03-15T09:00:00-05:00",
            "end_time": "2026-03-15T10:00:00-05:00",
        })
        assert action["tipo"] == "tool"
        assert action["name"] == "create_event"
        assert action["params"]["summary"] == "Reunion"
        assert action["params"]["user_google_email"] == _GOOGLE_EMAIL

    def test_get_events(self):
        action = tool_call_to_action("get_events", {
            "time_min": "2026-03-01T00:00:00-05:00",
            "time_max": "2026-03-31T23:59:59-05:00",
        })
        assert action["tipo"] == "tool"
        assert action["name"] == "get_events"
        assert "user_google_email" in action["params"]

    def test_send_email(self):
        action = tool_call_to_action("send_email", {
            "to": "test@example.com",
            "subject": "Test",
            "body": "Hello",
        })
        assert action["tipo"] == "tool"
        assert action["name"] == "send_email"
        assert action["params"]["to"] == "test@example.com"
        assert action["params"]["user_google_email"] == _GOOGLE_EMAIL

    def test_search_emails(self):
        action = tool_call_to_action("search_emails", {"query": "factura"})
        assert action["tipo"] == "tool"
        assert action["name"] == "search_emails"
        assert action["params"]["user_google_email"] == _GOOGLE_EMAIL

    def test_rpi_status_no_email(self):
        """rpi_status is MCP but NOT a workspace tool — no google email injection."""
        action = tool_call_to_action("rpi_status", {})
        assert action["tipo"] == "tool"
        assert action["name"] == "rpi_status"
        assert "user_google_email" not in action["params"]

    def test_search_drive_files(self):
        action = tool_call_to_action("search_drive_files", {"query": "presupuesto"})
        assert action["tipo"] == "tool"
        assert action["name"] == "search_drive_files"
        assert action["params"]["user_google_email"] == _GOOGLE_EMAIL


# =========================================================================
# Unknown tools — graceful fallback
# =========================================================================

class TestUnknownTools:
    def test_unknown_tool_passthrough(self):
        """Unknown tool names should pass through with tipo = tool_name."""
        action = tool_call_to_action("some_future_tool", {"key": "value"})
        assert action["tipo"] == "some_future_tool"
        assert action["key"] == "value"


# =========================================================================
# TOOLS schema validation
# =========================================================================

class TestToolSchemas:
    """Validate the TOOLS list structure itself."""

    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)
        assert len(TOOLS) > 0

    def test_all_tools_have_name_and_schema(self):
        for tool in TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool.get('name')} missing 'input_schema'"

    def test_all_tools_have_valid_schema_type(self):
        for tool in TOOLS:
            schema = tool["input_schema"]
            assert schema.get("type") == "object", (
                f"Tool {tool['name']} schema type should be 'object', got {schema.get('type')}"
            )

    def test_no_duplicate_tool_names(self):
        names = [t["name"] for t in TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names found: {names}"

    def test_all_tool_names_have_converter(self):
        """Every tool defined in TOOLS should be handled by tool_call_to_action."""
        for tool in TOOLS:
            name = tool["name"]
            # Just verify it doesn't crash — the result should always have 'tipo'
            action = tool_call_to_action(name, {})
            assert "tipo" in action, f"tool_call_to_action({name}) produced no 'tipo'"
