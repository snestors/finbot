import logging
from dataclasses import dataclass, field

from src.agent.tools import AgentTools
from src.services.currency import CurrencyService, SunatTipoCambio

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    response_text: str
    gasto_ids: list[str] = field(default_factory=list)


class Processor:
    def __init__(self, agent_parser, receipt_parser, gasto_repo,
                 ingreso_repo, budget_service, deuda_repo,
                 perfil_repo=None, cuenta_repo=None, presupuesto_repo=None,
                 mensaje_repo=None, document_parser=None, cobro_repo=None, tarjeta_repo=None):
        self.agent_parser = agent_parser
        self.receipt_parser = receipt_parser
        self.gasto_repo = gasto_repo
        self.ingreso_repo = ingreso_repo
        self.budget = budget_service
        self.deuda_repo = deuda_repo
        self.perfil_repo = perfil_repo
        self.cuenta_repo = cuenta_repo
        self.presupuesto_repo = presupuesto_repo
        self.mensaje_repo = mensaje_repo
        self.document_parser = document_parser
        self.tools = AgentTools()
        self.currency = CurrencyService()
        self.sunat = SunatTipoCambio()
        self.cobro_repo = cobro_repo
        self.tarjeta_repo = tarjeta_repo

    async def process(self, text: str, media: dict | None = None) -> ProcessResult:
        # --- MEDIA ---
        if media and media.get("mimetype"):
            mime = media["mimetype"]
            if "pdf" in mime or "spreadsheet" in mime or "excel" in mime:
                return await self._handle_document(media)
        if media and media.get("mimetype", "").startswith("image/"):
            return await self._handle_receipt(media)

        # --- TEXT ---
        if not text.strip():
            return ProcessResult(response_text="Envia un mensaje de texto o una foto de recibo.")

        # Build context + history for the agent
        context = await self._build_financial_context()
        history = await self._get_history()

        # Call AgentParser
        result = await self.agent_parser.parse(text, context=context, history=history)

        response = result.get("respuesta", "")
        acciones = result.get("acciones", [])
        gasto_ids = []

        # Execute each action
        for accion in acciones:
            action_result = await self._execute_action(accion)
            if action_result.get("gasto_id"):
                gasto_ids.append(action_result["gasto_id"])
            if action_result.get("data_response"):
                response += "\n\n" + action_result["data_response"]
            if action_result.get("alert"):
                response += "\n\n" + action_result["alert"]

        return ProcessResult(response_text=response, gasto_ids=gasto_ids)

    async def _handle_receipt(self, media: dict) -> ProcessResult:
        items = await self.receipt_parser.parse(
            image_b64=media["data"],
            mime_type=media["mimetype"],
        )
        gasto_ids = []
        lines = []
        total = 0

        for item in items.get("items", []):
            gasto_id = await self.gasto_repo.create(
                monto=item["monto"],
                categoria=item["categoria"],
                descripcion=item["descripcion"],
                fuente="recibo",
            )
            gasto_ids.append(gasto_id)
            lines.append(f"  | {item['categoria'].title()} S/{item['monto']:.2f} ({item['descripcion']})")
            total += item["monto"]

        establecimiento = items.get("establecimiento", "Recibo")
        response = f"Registre {len(items.get('items', []))} items de {establecimiento}:\n"
        response += "\n".join(lines)
        response += f"\n  Total: S/{total:.2f}"

        alertas = await self.budget.check_alerts_batch(items.get("items", []))
        if alertas:
            response += "\n\n" + "\n".join(alertas)

        return ProcessResult(response_text=response, gasto_ids=gasto_ids)


    async def _handle_document(self, media: dict) -> ProcessResult:
        if not self.document_parser:
            return ProcessResult(response_text="No puedo procesar documentos todavia.")
        parsed = await self.document_parser.parse(
            file_b64=media["data"],
            mime_type=media["mimetype"],
        )
        gasto_ids = []
        lines = []
        total = 0
        for item in parsed.get("items", []):
            gasto_id = await self.gasto_repo.create(
                monto=item["monto"],
                categoria=item.get("categoria", "otros"),
                descripcion=item.get("descripcion", ""),
                fuente="documento",
            )
            gasto_ids.append(gasto_id)
            cat = item.get("categoria", "otros").title()
            desc = item.get("descripcion", "")
            monto = item["monto"]
            lines.append(f"  | {cat} S/{monto:.2f} ({desc})")
            total += item["monto"]
        tipo = parsed.get("tipo_documento", "documento")
        emisor = parsed.get("emisor", "Documento")
        response = "Analice " + tipo + " de " + emisor + ":\n"
        if parsed.get("resumen"):
            response += parsed["resumen"] + "\n\n"
        if lines:
            response += "Registre:\n" + "\n".join(lines)
            response += "\n  Total: S/" + f"{total:.2f}"
        elif not parsed.get("items"):
            response += parsed.get("resumen", "No encontre items financieros.")
        alertas = await self.budget.check_alerts_batch(parsed.get("items", []))
        if alertas:
            response += "\n\n" + "\n".join(alertas)
        return ProcessResult(response_text=response, gasto_ids=gasto_ids)

    async def _build_financial_context(self) -> str:
        parts = []

        # Profile
        if self.perfil_repo:
            perfil = await self.perfil_repo.get()
            if perfil:
                nombre = perfil.get("nombre") or "Usuario"
                moneda = perfil.get("moneda_default", "PEN")
                onboarding = "si" if perfil.get("onboarding_completo") else "no"
                parts.append(f"Perfil: nombre={nombre}, moneda={moneda}, onboarding_completo={onboarding}")
            else:
                parts.append("Perfil: NO EXISTE (usuario nuevo, hacer onboarding)")

        # Today's expenses
        try:
            gastos_hoy = await self.gasto_repo.get_today()
            total_hoy = sum(g["monto"] for g in gastos_hoy)
            parts.append(f"Gastos hoy: {len(gastos_hoy)} gastos, total S/{total_hoy:.2f}")
        except Exception:
            pass

        # Active budgets
        if self.presupuesto_repo:
            try:
                presupuestos = await self.presupuesto_repo.get_all()
                if presupuestos:
                    budget_lines = []
                    for p in presupuestos:
                        total = await self.gasto_repo.total_categoria_mes(p["categoria"])
                        pct = (total / p["limite_mensual"] * 100) if p["limite_mensual"] > 0 else 0
                        budget_lines.append(f"  {p['categoria']}: S/{total:.0f}/S/{p['limite_mensual']:.0f} ({pct:.0f}%)")
                    parts.append("Presupuestos:\n" + "\n".join(budget_lines))
            except Exception:
                pass

        # Active debts
        try:
            deudas = await self.deuda_repo.get_all()
            if deudas:
                total_deudas = sum(d["saldo_actual"] for d in deudas)
                deuda_lines = []
                for d in deudas:
                    entidad = f" ({d['entidad']})" if d.get("entidad") else ""
                    cuotas = f" [{d.get('cuotas_pagadas', 0)}/{d['cuotas_total']}]" if d.get("cuotas_total") else ""
                    deuda_lines.append(f"  {d['nombre']}{entidad}: S/{d['saldo_actual']:.2f}{cuotas}")
                parts.append(f"Deudas activas ({len(deudas)}), total S/{total_deudas:.2f}:\n" + "\n".join(deuda_lines))
        except Exception:
            pass

        # Accounts
        if self.cuenta_repo:
            try:
                cuentas = await self.cuenta_repo.get_all()
                if cuentas:
                    cuenta_lines = [f"  {c['nombre']} ({c['tipo']}): {c['moneda']} {c['saldo']:.2f}" for c in cuentas]
                    parts.append("Cuentas:\n" + "\n".join(cuenta_lines))
            except Exception:
                pass

        return "\n".join(parts)

    async def _get_history(self) -> list[dict]:
        if not self.mensaje_repo:
            return []
        try:
            return await self.mensaje_repo.get_history(limit=20)
        except Exception:
            return []

    async def _execute_action(self, accion: dict) -> dict:
        tipo = accion.get("tipo", "")
        result = {}

        try:
            if tipo == "gasto":
                perfil = await self.perfil_repo.get() if self.perfil_repo else None
                moneda = accion.get("moneda") or (perfil.get("moneda_default", "PEN") if perfil else "PEN")
                gasto_id = await self.gasto_repo.create(
                    monto=accion["monto"],
                    categoria=accion.get("categoria", "otros"),
                    descripcion=accion.get("descripcion", ""),
                    fuente="texto",
                    moneda=moneda,
                    comercio=accion.get("comercio"),
                    metodo_pago=accion.get("metodo_pago"),
                    cuenta_id=accion.get("cuenta_id"),
                )
                result["gasto_id"] = gasto_id

                # Check budget alert
                alerta = await self.budget.check_alert(accion.get("categoria", "otros"))
                if alerta:
                    result["alert"] = alerta

                # Update account balance if specified
                if accion.get("cuenta_id") and self.cuenta_repo:
                    await self.cuenta_repo.update_saldo(accion["cuenta_id"], -accion["monto"])

            elif tipo == "ingreso":
                perfil = await self.perfil_repo.get() if self.perfil_repo else None
                moneda = accion.get("moneda") or (perfil.get("moneda_default", "PEN") if perfil else "PEN")
                await self.ingreso_repo.create(
                    monto=accion["monto"],
                    fuente=accion.get("fuente", accion.get("descripcion", "")),
                    descripcion=accion.get("descripcion", ""),
                    moneda=moneda,
                    cuenta_id=accion.get("cuenta_id"),
                )
                if accion.get("cuenta_id") and self.cuenta_repo:
                    await self.cuenta_repo.update_saldo(accion["cuenta_id"], accion["monto"])

            elif tipo == "consulta":
                periodo = accion.get("periodo", "hoy")
                if periodo == "hoy":
                    result["data_response"] = await self.gasto_repo.resumen_hoy()
                elif periodo == "semana":
                    result["data_response"] = await self.gasto_repo.resumen_semana()
                elif periodo == "mes":
                    result["data_response"] = await self.gasto_repo.resumen_mes()
                elif periodo == "deudas":
                    result["data_response"] = await self.deuda_repo.resumen()
                elif periodo == "cobros" and self.cobro_repo:
                    result["data_response"] = await self.cobro_repo.resumen()
                elif periodo == "tarjetas" and self.tarjeta_repo:
                    tarjetas = await self.tarjeta_repo.get_all()
                    if tarjetas:
                        lines = ["Tus tarjetas:"]
                        for t in tarjetas:
                            lines.append(f"  | {t['nombre']} ({t['banco']}) *{t['ultimos_4']} - Limite: {t['moneda']} {t['limite_credito']:.2f}")
                        result["data_response"] = "\n".join(lines)
                    else:
                        result["data_response"] = "No tienes tarjetas registradas."
                elif periodo == "cuentas" and self.cuenta_repo:
                    cuentas = await self.cuenta_repo.get_all()
                    if cuentas:
                        lines = ["Tus cuentas:"]
                        for c in cuentas:
                            lines.append(f"  | {c['nombre']} ({c['tipo']}): {c['moneda']} {c['saldo']:.2f}")
                        result["data_response"] = "\n".join(lines)
                    else:
                        result["data_response"] = "No tienes cuentas registradas."

            elif tipo == "set_presupuesto":
                if self.presupuesto_repo:
                    await self.presupuesto_repo.save({
                        "categoria": accion["categoria"],
                        "limite_mensual": accion["limite"],
                        "alerta_porcentaje": accion.get("alerta_porcentaje", 80),
                    })

            elif tipo == "agregar_deuda":
                await self.deuda_repo.save({
                    "nombre": accion["nombre"],
                    "saldo_actual": accion.get("saldo", 0),
                    "entidad": accion.get("entidad"),
                    "cuotas_total": accion.get("cuotas_total", 0),
                    "cuotas_pagadas": accion.get("cuotas_pagadas", 0),
                    "cuota_monto": accion.get("cuota_monto", 0),
                    "tasa_interes_mensual": accion.get("tasa", 0),
                    "pago_minimo": accion.get("pago_minimo", 0),
                })

            elif tipo == "pago_deuda":
                deuda_id = accion.get("deuda_id")
                if not deuda_id and accion.get("nombre"):
                    # Find by name
                    deudas = await self.deuda_repo.get_all()
                    nombre_lower = accion["nombre"].lower()
                    for d in deudas:
                        if nombre_lower in d["nombre"].lower():
                            deuda_id = d["id"]
                            break
                if deuda_id:
                    await self.deuda_repo.registrar_pago(deuda_id, accion["monto"])

            elif tipo == "set_perfil":
                if self.perfil_repo:
                    update_data = {}
                    if accion.get("nombre"):
                        update_data["nombre"] = accion["nombre"]
                    if accion.get("moneda_default"):
                        update_data["moneda_default"] = accion["moneda_default"]
                    if accion.get("onboarding_completo"):
                        update_data["onboarding_completo"] = 1
                    if update_data:
                        await self.perfil_repo.create_or_update(update_data)

            elif tipo == "crear_cuenta":
                if self.cuenta_repo:
                    await self.cuenta_repo.save({
                        "nombre": accion["nombre"],
                        "tipo": accion.get("tipo_cuenta", "efectivo"),
                        "moneda": accion.get("moneda", "PEN"),
                        "saldo": accion.get("saldo", 0),
                    })

            elif tipo == "consulta_cambio":
                monto = accion.get("monto", 1.0)
                de = accion.get("de", "USD")
                a = accion.get("a", "PEN")
                converted = await self.currency.convert(monto, de, a)
                rate = await self.currency.get_rate(de, a)
                result["data_response"] = f"{de} {monto:.2f} = {a} {converted:.2f} (tasa: 1 {de} = {rate:.4f} {a})"

            elif tipo == "tool":
                tool_name = accion.get("name", "")
                params = accion.get("params", {})
                tool_result = self.tools.execute(tool_name, params)
                result["data_response"] = tool_result

            elif tipo == "cobro":
                if self.cobro_repo:
                    await self.cobro_repo.save({
                        "deudor": accion["deudor"],
                        "concepto": accion.get("concepto", ""),
                        "monto_total": accion["monto"],
                        "moneda": accion.get("moneda", "PEN"),
                    })

            elif tipo == "pago_cobro":
                if self.cobro_repo:
                    cobros = await self.cobro_repo.get_by_deudor(accion.get("nombre", ""))
                    if cobros:
                        updated = await self.cobro_repo.registrar_pago(cobros[0]["id"], accion["monto"])
                        result["data_response"] = f"Pago registrado. {updated.get('deudor', '')} debe ahora S/{updated.get('saldo_pendiente', 0):.2f}"
                    else:
                        result["data_response"] = "No encontre cobros para ese deudor."

            elif tipo == "tipo_cambio_sunat":
                tc = await self.sunat.get_tipo_cambio()
                result["data_response"] = f"Tipo de cambio SUNAT ({tc['fuente']}):\nCompra: S/{tc['compra']}\nVenta: S/{tc['venta']}"


            elif tipo == "tarjeta":
                if self.tarjeta_repo:
                    await self.tarjeta_repo.save({
                        "nombre": accion["nombre"],
                        "banco": accion.get("banco", ""),
                        "tipo": accion.get("tipo_tarjeta", "credito"),
                        "ultimos_4": accion.get("ultimos_4", ""),
                        "limite_credito": accion.get("limite_credito", 0),
                        "fecha_corte": accion.get("fecha_corte", 1),
                        "fecha_pago": accion.get("fecha_pago", 15),
                    })

            elif tipo == "eliminar_gasto":
                if accion.get("gasto_id"):
                    await self.gasto_repo.delete(accion["gasto_id"])

        except Exception as e:
            logger.error(f"Error executing action {tipo}: {e}")

        return result
