"""Specialized context builders for each agent. Only loads relevant data.

Active (used by unified_agent.py):
  - build_finance_context
  - build_energy_context
  - build_printer_context

DEPRECATED (only used by legacy agents when UNIFIED_AGENT_ENABLED=False):
  - build_analysis_context
  - build_admin_context
  - build_chat_context
"""
import logging

logger = logging.getLogger(__name__)

_TIPO_LABELS = {
    "gasto": "G", "ingreso": "I", "pago_tarjeta": "PT",
    "transferencia": "T", "pago_deuda": "PD", "pago_cobro": "PC",
}


async def build_finance_context(repos: dict) -> str:
    """Context for FinanceAgent: profile, today's movements with IDs, accounts, cards, debts, cobros."""
    parts = []

    # Profile (minimal)
    perfil_repo = repos.get("perfil")
    if perfil_repo:
        perfil = await perfil_repo.get()
        if perfil:
            parts.append(f"Perfil: nombre={perfil.get('nombre', 'Usuario')}, moneda={perfil.get('moneda_default', 'PEN')}")

    # Today's movements WITH IDs (essential for corrections/deletions)
    mov_repo = repos.get("movimiento")
    if mov_repo:
        try:
            movs_hoy = await mov_repo.get_today()
            movs_hoy.sort(key=lambda g: g["id"])
            gastos_hoy = [m for m in movs_hoy if m["tipo"] == "gasto"]
            total_hoy = sum(g["monto"] for g in gastos_hoy)
            if gastos_hoy:
                parts.append(f"Gastos hoy: {len(gastos_hoy)} gastos, total S/{total_hoy:.2f}")
                detail_lines = []
                for g in gastos_hoy[:25]:
                    desc = g.get("descripcion", "")
                    comercio = f" en {g['comercio']}" if g.get("comercio") else ""
                    pago = f" [{g['metodo_pago']}]" if g.get("metodo_pago") else ""
                    cuenta = f" cuenta:{g['cuenta_id']}" if g.get("cuenta_id") else ""
                    tarjeta = f" tarjeta:{g['tarjeta_id']}" if g.get("tarjeta_id") else ""
                    cuotas_txt = f" ({g['cuotas']} cuotas)" if g.get("cuotas") and g["cuotas"] > 1 else ""
                    cat = g.get("categoria") or "otros"
                    detail_lines.append(
                        f"  #{g['id']} {cat} S/{g['monto']:.2f} {desc}{comercio}{pago}{cuenta}{tarjeta}{cuotas_txt}"
                    )
                parts.append("Detalle gastos hoy:\n" + "\n".join(detail_lines))
                if len(gastos_hoy) > 25:
                    parts.append(f"  ...y {len(gastos_hoy) - 25} gastos mas")
            else:
                parts.append("Gastos hoy: 0")

            # Other movements today
            otros = [m for m in movs_hoy if m["tipo"] != "gasto"]
            if otros:
                other_lines = []
                for m in otros[:10]:
                    label = _TIPO_LABELS.get(m["tipo"], m["tipo"])
                    desc = m.get("descripcion", "")
                    other_lines.append(f"  #{m['id']} [{label}] S/{m['monto']:.2f} {desc}")
                parts.append("Otros movimientos hoy:\n" + "\n".join(other_lines))
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # This month's income WITH IDs
    if mov_repo:
        try:
            ingresos_mes = await mov_repo.get_ingresos_mes()
            if ingresos_mes:
                total_ingresos = sum(i["monto"] for i in ingresos_mes)
                parts.append(f"Ingresos del mes: {len(ingresos_mes)}, total S/{total_ingresos:.2f}")
                for i in ingresos_mes[:15]:
                    desc = i.get("descripcion", "")
                    cuenta = f" cuenta:{i['cuenta_id']}" if i.get("cuenta_id") else ""
                    fecha = i.get("fecha", "")[:10]
                    moneda = i.get("moneda", "PEN")
                    parts.append(f"  #{i['id']} {fecha} {moneda} {i['monto']:.2f} {desc}{cuenta}")
            else:
                parts.append("Ingresos del mes: 0")
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Accounts with payment methods
    cuenta_repo = repos.get("cuenta")
    if cuenta_repo:
        try:
            cuentas = await cuenta_repo.get_all()
            if cuentas:
                cuenta_lines = []
                for c in cuentas:
                    metodos = c.get("metodos_pago", [])
                    met = f" metodos:[{','.join(metodos)}]" if metodos else ""
                    cuenta_lines.append(f"  id={c['id']} {c['nombre']} ({c['tipo']}): {c['moneda']} {c['saldo']:.2f}{met}")
                parts.append("Cuentas:\n" + "\n".join(cuenta_lines))
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Credit cards
    tarjeta_repo = repos.get("tarjeta")
    if tarjeta_repo:
        try:
            tarjetas = await tarjeta_repo.get_all()
            if tarjetas:
                tj_lines = []
                for t in tarjetas:
                    usado = t.get("saldo_usado", 0) or 0
                    limite = t.get("limite_credito", 0) or 0
                    disponible = limite - usado
                    corte = t.get("fecha_corte", "?")
                    pago_d = t.get("fecha_pago", "?")
                    tj_lines.append(
                        f"  id={t['id']} {t['nombre']} ({t['banco']}) *{t['ultimos_4']}"
                        f" - Limite: {t['moneda']} {limite:.2f}, Usado: {usado:.2f}, Disponible: {disponible:.2f}"
                        f" | corte: dia {corte}, pago: dia {pago_d}"
                    )
                parts.append("Tarjetas:\n" + "\n".join(tj_lines))
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Active debts (compact)
    deuda_repo = repos.get("deuda")
    if deuda_repo:
        try:
            deudas = await deuda_repo.get_all()
            if deudas:
                total_deudas = sum(d["saldo_actual"] for d in deudas)
                deuda_lines = []
                for d in deudas:
                    entidad = f" ({d['entidad']})" if d.get("entidad") else ""
                    cuotas = f" [{d.get('cuotas_pagadas', 0)}/{d['cuotas_total']} cuotas]" if d.get("cuotas_total") else ""
                    deuda_lines.append(f"  id={d['id']} {d['nombre']}{entidad}: S/{d['saldo_actual']:.2f}{cuotas}")
                parts.append(f"Deudas ({len(deudas)}), total S/{total_deudas:.2f}:\n" + "\n".join(deuda_lines))
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Pending cobros (compact)
    cobro_repo = repos.get("cobro")
    if cobro_repo:
        try:
            cobros = await cobro_repo.get_all(solo_pendientes=True)
            if cobros:
                total_cobros = sum(c["saldo_pendiente"] for c in cobros)
                cobro_lines = []
                for c in cobros:
                    concepto = f" ({c['concepto']})" if c.get("concepto") else ""
                    cobro_lines.append(f"  id={c['id']} {c['deudor']}: S/{c['saldo_pendiente']:.2f} de S/{c['monto_total']:.2f}{concepto}")
                parts.append(f"Cobros pendientes ({len(cobros)}), total S/{total_cobros:.2f}:\n" + "\n".join(cobro_lines))
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    return "\n".join(parts)


async def build_energy_context(repos: dict) -> str:
    """Context for energy analysis: live data, today's consumption, monthly summary, config, last payment."""
    parts = []

    # Live Sonoff data (real-time, updates every ~1s)
    sonoff = repos.get("sonoff_service")
    if sonoff and sonoff.latest:
        d = sonoff.latest
        parts.append(
            f"EN VIVO ahora: {d.get('power_w', 0):.1f}W, "
            f"{d.get('voltage_v', 0):.1f}V, {d.get('current_a', 0):.2f}A, "
            f"hoy {d.get('day_kwh', 0):.2f} kWh, mes {d.get('month_kwh', 0):.2f} kWh"
        )

    consumo_repo = repos.get("consumo")
    if consumo_repo:
        try:
            hoy = await consumo_repo.get_hoy_resumen()
            if hoy and hoy.get("lecturas"):
                parts.append(
                    f"Historial hoy: {hoy.get('day_kwh', 0):.2f} kWh, "
                    f"potencia promedio {hoy.get('avg_power', 0):.0f}W, "
                    f"pico {hoy.get('max_power', 0):.0f}W, "
                    f"corriente promedio {hoy.get('avg_current', 0):.2f}A "
                    f"({hoy.get('lecturas', 0)} lecturas en DB)"
                )
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

        try:
            mes_res = await consumo_repo.get_mes_resumen_energia()
            if mes_res and mes_res.get("kwh_total", 0) > 0:
                parts.append(
                    f"Historial mes: {mes_res.get('kwh_total', 0):.2f} kWh en {mes_res.get('dias', 0)} dias"
                )
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    config_repo = repos.get("consumo_config")
    if config_repo:
        try:
            costo = await config_repo.get_float("costo_kwh_luz", 0.75)
            parts.append(f"Costo por kWh: S/{costo:.4f}")

            # Estimate monthly cost from live data or DB
            month_kwh = 0.0
            if sonoff and sonoff.latest:
                month_kwh = sonoff.latest.get("month_kwh", 0)
            if month_kwh > 0:
                estimado = month_kwh * costo
                parts.append(f"Costo estimado mes: S/{estimado:.2f} (basado en {month_kwh:.2f} kWh del medidor)")
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    pago_repo = repos.get("pago_consumo")
    if pago_repo:
        try:
            ultimo = await pago_repo.get_ultimo("luz")
            if ultimo:
                parts.append(
                    f"Ultimo pago luz: S/{ultimo['monto']:.2f} el {ultimo['fecha_pago']}"
                    f" ({ultimo.get('kwh_periodo', 0) or 0:.1f} kWh, "
                    f"S/{ultimo.get('costo_kwh', 0) or 0:.4f}/kWh)"
                )
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    return "\n".join(parts)


async def build_analysis_context(repos: dict) -> str:
    """DEPRECATED: Only used by legacy AnalysisAgent. UnifiedAgent builds its own context.
    Context for AnalysisAgent: summaries, budgets, account totals. No individual IDs."""
    parts = []

    # Profile
    perfil_repo = repos.get("perfil")
    if perfil_repo:
        perfil = await perfil_repo.get()
        if perfil:
            parts.append(f"Perfil: nombre={perfil.get('nombre', 'Usuario')}, moneda={perfil.get('moneda_default', 'PEN')}")

    mov_repo = repos.get("movimiento")
    if mov_repo:
        # Today summary
        try:
            gastos_hoy = await mov_repo.get_gastos_hoy()
            total_hoy = sum(g["monto"] for g in gastos_hoy)
            by_cat: dict[str, float] = {}
            for g in gastos_hoy:
                cat = g.get("categoria") or "otros"
                by_cat[cat] = by_cat.get(cat, 0) + g["monto"]
            if gastos_hoy:
                cat_summary = ", ".join(f"{c}: S/{v:.2f}" for c, v in sorted(by_cat.items(), key=lambda x: -x[1]))
                parts.append(f"Hoy: {len(gastos_hoy)} gastos, S/{total_hoy:.2f} ({cat_summary})")
            else:
                parts.append("Hoy: 0 gastos")
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

        # Weekly/Monthly summaries
        try:
            parts.append(await mov_repo.resumen_semana())
        except Exception as e:
            logger.warning(f"context_builders error: {e}")
        try:
            parts.append(await mov_repo.resumen_mes())
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Budget progress
    presupuesto_repo = repos.get("presupuesto")
    if presupuesto_repo and mov_repo:
        try:
            presupuestos = await presupuesto_repo.get_all()
            if presupuestos:
                budget_lines = []
                for p in presupuestos:
                    total = await mov_repo.total_categoria_mes(p["categoria"])
                    pct = (total / p["limite_mensual"] * 100) if p["limite_mensual"] > 0 else 0
                    budget_lines.append(f"  {p['categoria']}: S/{total:.0f}/S/{p['limite_mensual']:.0f} ({pct:.0f}%)")
                parts.append("Presupuestos:\n" + "\n".join(budget_lines))
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Account balances
    cuenta_repo = repos.get("cuenta")
    if cuenta_repo:
        try:
            cuentas = await cuenta_repo.get_all()
            if cuentas:
                cuenta_lines = [f"  {c['nombre']}: {c['moneda']} {c['saldo']:.2f}" for c in cuentas]
                parts.append("Saldos cuentas:\n" + "\n".join(cuenta_lines))
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Debt summary
    deuda_repo = repos.get("deuda")
    if deuda_repo:
        try:
            deudas = await deuda_repo.get_all()
            if deudas:
                total = sum(d["saldo_actual"] for d in deudas)
                parts.append(f"Deudas: {len(deudas)} activas, total S/{total:.2f}")
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Card summary
    tarjeta_repo = repos.get("tarjeta")
    if tarjeta_repo:
        try:
            tarjetas = await tarjeta_repo.get_all()
            if tarjetas:
                total_usado = sum(t.get("saldo_usado", 0) or 0 for t in tarjetas)
                parts.append(f"Tarjetas: {len(tarjetas)} activas, total usado S/{total_usado:.2f}")
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Cobros summary
    cobro_repo = repos.get("cobro")
    if cobro_repo:
        try:
            cobros = await cobro_repo.get_all(solo_pendientes=True)
            if cobros:
                total = sum(c["saldo_pendiente"] for c in cobros)
                parts.append(f"Cobros: {len(cobros)} pendientes, total S/{total:.2f}")
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Energy context
    try:
        energy = await build_energy_context(repos)
        if energy:
            parts.append(energy)
    except Exception:
        pass

    # 3D Printer context
    try:
        printer = build_printer_context(repos)
        if printer:
            parts.append(printer)
    except Exception:
        pass

    return "\n".join(parts)


async def build_admin_context(repos: dict, registry_info: list[dict] = None,
                              mcp_tools: str = "") -> str:
    """DEPRECATED: Only used by legacy AdminAgent. UnifiedAgent builds its own context.
    Context for AdminAgent: profile, memory, reminders, agent registry, MCP tools."""
    parts = []

    # Profile
    perfil_repo = repos.get("perfil")
    if perfil_repo:
        perfil = await perfil_repo.get()
        if perfil:
            nombre = perfil.get("nombre") or "Usuario"
            moneda = perfil.get("moneda_default", "PEN")
            onboarding = "si" if perfil.get("onboarding_completo") else "no"
            parts.append(f"Perfil: nombre={nombre}, moneda={moneda}, onboarding={onboarding}")
        else:
            parts.append("Perfil: NO EXISTE (usuario nuevo)")

    # Persistent memory
    memoria_repo = repos.get("memoria")
    if memoria_repo:
        try:
            mem_context = await memoria_repo.format_for_context()
            if mem_context:
                parts.append(mem_context)
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Agent registry info
    if registry_info:
        agent_lines = [f"  {a['name']}: {a['prompt_file']} ({a['prompt_size']}B)" for a in registry_info]
        parts.append("Agentes registrados:\n" + "\n".join(agent_lines))

    # Plugin info
    try:
        from pathlib import Path
        plugins_dir = Path(__file__).parent.parent.parent / "plugins"
        if plugins_dir.exists():
            plugin_files = [f.name for f in sorted(plugins_dir.glob("*.py")) if not f.name.startswith("_")]
            if plugin_files:
                parts.append("Plugins instalados: " + ", ".join(plugin_files))
            else:
                parts.append("Plugins: ninguno instalado (crear en plugins/)")
    except Exception:
        pass

    # MCP tools
    if mcp_tools:
        parts.append(mcp_tools)

    return "\n".join(parts)


def build_printer_context(repos: dict) -> str:
    """Context for 3D printer status (sync — reads from in-memory latest)."""
    printer = repos.get("printer_service")
    if not printer or not printer.latest:
        return ""
    return printer.get_summary()


async def build_chat_context(repos: dict) -> str:
    """DEPRECATED: Only used by legacy ChatAgent. UnifiedAgent builds its own context.
    Context for ChatAgent: minimal — profile, memory, today summary."""
    parts = []

    # Profile (or NOT EXISTS for onboarding)
    perfil_repo = repos.get("perfil")
    if perfil_repo:
        perfil = await perfil_repo.get()
        if perfil:
            nombre = perfil.get("nombre") or "Usuario"
            moneda = perfil.get("moneda_default", "PEN")
            parts.append(f"Perfil: nombre={nombre}, moneda={moneda}")
        else:
            parts.append("Perfil: NO EXISTE (hacer onboarding — pedir nombre y moneda)")

    # Memory
    memoria_repo = repos.get("memoria")
    if memoria_repo:
        try:
            mem_context = await memoria_repo.format_for_context()
            if mem_context:
                parts.append(mem_context)
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    # Today summary (just count + total)
    mov_repo = repos.get("movimiento")
    if mov_repo:
        try:
            gastos_hoy = await mov_repo.get_gastos_hoy()
            total_hoy = sum(g["monto"] for g in gastos_hoy)
            parts.append(f"Gastos hoy: {len(gastos_hoy)} gastos, S/{total_hoy:.2f}")
        except Exception as e:
            logger.warning(f"context_builders error: {e}")

    return "\n".join(parts)
