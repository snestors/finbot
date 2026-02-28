"""ActionExecutor — executes actions from any agent. Uses handler registry + unified movimientos."""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.agent.tools import AgentTools
from src.agent.plugin_manager import PluginManager
from src.config import settings
from src.services.currency import CurrencyService, SunatTipoCambio

logger = logging.getLogger(__name__)

# Movement types that map to the unified movimientos table
_MOV_TYPES = {"gasto", "ingreso", "pago_tarjeta", "transferencia", "pago_deuda", "pago_cobro"}


class ActionExecutor:
    """Executes parsed actions. Shared across all agents."""

    def __init__(self, repos: dict, tools: AgentTools = None,
                 currency_service: CurrencyService = None,
                 sunat_service: SunatTipoCambio = None,
                 budget_service=None,
                 gasto_cuota_repo=None,
                 movimiento_cuota_repo=None,
                 tarjeta_periodo_repo=None):
        self.repos = repos
        self.tools = tools or AgentTools()
        self.currency = currency_service or CurrencyService()
        self.sunat = sunat_service or SunatTipoCambio()
        self.budget = budget_service
        self.gasto_cuota_repo = gasto_cuota_repo
        self.movimiento_cuota_repo = movimiento_cuota_repo
        self.tarjeta_periodo_repo = tarjeta_periodo_repo

        # Load plugins
        self.plugins = PluginManager()
        self.plugins.load_all()

        # Handler registry
        self._handlers = {
            # Unified movimiento (new)
            "movimiento": self._do_movimiento,
            "actualizar_movimiento": self._do_actualizar_movimiento,
            "eliminar_movimiento": self._do_eliminar_movimiento,
            "eliminar_movimientos": self._do_eliminar_movimientos,
            "importar_estado_cuenta": self._do_importar_estado_cuenta,
            # Legacy adapters (redirect to movimiento)
            "gasto": self._do_legacy_gasto,
            "ingreso": self._do_legacy_ingreso,
            "transferencia": self._do_legacy_transferencia,
            "pago_tarjeta": self._do_legacy_pago_tarjeta,
            "pago_deuda": self._do_legacy_pago_deuda,
            "pago_cobro": self._do_legacy_pago_cobro,
            # Legacy gasto management (redirect to movimiento)
            "actualizar_gasto": self._do_legacy_actualizar_gasto,
            "eliminar_gasto": self._do_legacy_eliminar_gasto,
            "eliminar_gastos": self._do_legacy_eliminar_gastos,
            "eliminar_gastos_excepto": self._do_legacy_eliminar_gastos_excepto,
            "eliminar_gastos_periodo": self._do_legacy_eliminar_gastos_periodo,
            "actualizar_ingreso": self._do_legacy_actualizar_ingreso,
            "eliminar_ingreso": self._do_legacy_eliminar_ingreso,
            # Non-movimiento actions (unchanged)
            "buscar_gasto": self._do_buscar_gasto,
            "consulta": self._do_consulta,
            "set_presupuesto": self._do_set_presupuesto,
            "agregar_deuda": self._do_agregar_deuda,
            "set_perfil": self._do_set_perfil,
            "crear_cuenta": self._do_crear_cuenta,
            "actualizar_cuenta": self._do_actualizar_cuenta,
            "consulta_cambio": self._do_consulta_cambio,
            "tool": self._do_tool,
            "cobro": self._do_cobro,
            "tipo_cambio_sunat": self._do_tipo_cambio_sunat,
            "tarjeta": self._do_tarjeta,
            "memorizar": self._do_memorizar,
            "recordatorio": self._do_recordatorio,
            "consulta_consumo": self._do_consulta_consumo,
        }

    async def execute(self, accion: dict) -> dict:
        """Execute a single action. Checks built-in handlers first, then plugins."""
        tipo = accion.get("tipo", "")
        handler = self._handlers.get(tipo)

        # Check plugins for unknown action types
        if not handler:
            self.plugins.reload_all()  # Hot-reload
            plugin_handler = self.plugins.get_action_handler(tipo)
            if plugin_handler:
                try:
                    return await plugin_handler(accion, self.repos)
                except Exception as e:
                    logger.error(f"Plugin action {tipo} error: {e}", exc_info=True)
                    return {"data_response": f"Error en plugin {tipo}: {e}"}

            logger.warning(f"Unknown action type: {tipo}")
            return {}

        try:
            return await handler(accion)
        except Exception as e:
            logger.error(f"Error executing action {tipo}: {e}", exc_info=True)
            return {}

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _convert_to_account_currency(self, monto: float, moneda: str, cuenta_id: int) -> float:
        cuenta_repo = self.repos.get("cuenta")
        if not cuenta_id or not cuenta_repo:
            return monto
        cuenta = await cuenta_repo.get_by_id(cuenta_id)
        if not cuenta:
            return monto
        cuenta_moneda = cuenta.get("moneda", "PEN")
        if moneda.upper() == cuenta_moneda.upper():
            return monto
        try:
            return await self.currency.convert(monto, moneda, cuenta_moneda)
        except Exception:
            try:
                tc = await self.sunat.get_tipo_cambio()
                if moneda.upper() == "USD" and cuenta_moneda.upper() == "PEN":
                    return round(monto * float(tc["venta"]), 2)
                elif moneda.upper() == "PEN" and cuenta_moneda.upper() == "USD":
                    return round(monto / float(tc["compra"]), 2)
            except Exception:
                pass
            return monto

    async def _auto_link_cuenta(self, accion: dict) -> int | None:
        if accion.get("cuenta_id"):
            return accion.get("cuenta_id")
        cuenta_repo = self.repos.get("cuenta")
        if not cuenta_repo:
            return None
        metodo = accion.get("metodo_pago", "")
        if metodo:
            cuenta = await cuenta_repo.get_by_metodo_pago(metodo)
            if cuenta:
                return cuenta["id"]
        return None

    async def _get_perfil_moneda(self) -> str:
        perfil_repo = self.repos.get("perfil")
        if perfil_repo:
            perfil = await perfil_repo.get()
            if perfil:
                return perfil.get("moneda_default", "PEN")
        return "PEN"

    def _resolve_fecha(self, fecha_str: str | None) -> datetime | None:
        if not fecha_str:
            return None
        now = datetime.now(ZoneInfo(settings.timezone))
        f = fecha_str.strip().lower()
        if f == "ayer":
            return now - timedelta(days=1)
        if f in ("anteayer", "ante ayer"):
            return now - timedelta(days=2)
        if f.startswith("hace "):
            try:
                parts = f.split()
                dias = int(parts[1])
                return now - timedelta(days=dias)
            except (IndexError, ValueError):
                pass
        try:
            dt = datetime.strptime(fecha_str.strip(), "%Y-%m-%d")
            return dt.replace(tzinfo=ZoneInfo(settings.timezone))
        except ValueError:
            pass
        return None

    async def _resolve_tarjeta_periodo(self, tarjeta_id: int, fecha_dt: datetime = None):
        """Auto-assign tarjeta_periodo_id for credit card charges."""
        if not self.tarjeta_periodo_repo or not tarjeta_id:
            return None
        tarjeta_repo = self.repos.get("tarjeta")
        if not tarjeta_repo:
            return None
        tarjeta = await tarjeta_repo.get_by_id(tarjeta_id)
        if not tarjeta:
            return None
        target_date = (fecha_dt or datetime.now(ZoneInfo(settings.timezone))).date()
        period = tarjeta_repo.get_billing_period(tarjeta, target_date)
        tp = await self.tarjeta_periodo_repo.get_or_create(
            tarjeta_id=tarjeta_id,
            periodo=period["periodo"],
            fecha_inicio=period["inicio"],
            fecha_fin=period["fin"],
            fecha_pago=period["fecha_pago"],
        )
        return tp["id"]

    async def _delete_movimiento(self, mov_id: int):
        """Delete a movimiento and its cuotas."""
        mov_repo = self.repos.get("movimiento")
        if not mov_repo:
            return
        mov = await mov_repo.get_by_id(mov_id)
        if not mov:
            return
        if self.movimiento_cuota_repo:
            try:
                await self.movimiento_cuota_repo.delete_by_movimiento(mov_id)
            except Exception:
                pass
        await mov_repo.delete(mov_id)

    # =========================================================================
    # Unified Movimiento handler
    # =========================================================================

    async def _do_movimiento(self, accion: dict) -> dict:
        """Unified handler for all movement types."""
        mov_tipo = accion.get("mov_tipo", "gasto")
        monto = accion["monto"]
        moneda = accion.get("moneda") or await self._get_perfil_moneda()
        mov_repo = self.repos["movimiento"]

        # Resolve cuenta
        cuenta_id = await self._auto_link_cuenta(accion)
        cuenta_destino_id = accion.get("cuenta_destino_id")

        # Currency conversion
        monto_cuenta = monto
        monto_destino = None
        if mov_tipo == "transferencia":
            monto_cuenta = await self._convert_to_account_currency(monto, moneda, cuenta_id)
            monto_destino = await self._convert_to_account_currency(monto, moneda, cuenta_destino_id)
        elif cuenta_id:
            monto_cuenta = await self._convert_to_account_currency(monto, moneda, cuenta_id)

        # Resolve date
        fecha_dt = self._resolve_fecha(accion.get("fecha"))
        now = datetime.now(ZoneInfo(settings.timezone))
        dt = fecha_dt or now
        fecha = dt.isoformat()
        mes = dt.strftime("%Y-%m")
        semana = dt.strftime("%Y-W%V")

        # Resolve tarjeta_periodo for credit card charges
        tarjeta_id = accion.get("tarjeta_id")
        tarjeta_periodo_id = None
        if mov_tipo == "gasto" and tarjeta_id:
            tarjeta_periodo_id = await self._resolve_tarjeta_periodo(tarjeta_id, dt)
        elif mov_tipo == "pago_tarjeta" and tarjeta_id:
            # Apply payment to oldest billed period
            if self.tarjeta_periodo_repo:
                oldest = await self.tarjeta_periodo_repo.get_oldest_facturado(tarjeta_id)
                if oldest:
                    tarjeta_periodo_id = oldest["id"]
                    await self.tarjeta_periodo_repo.registrar_pago(oldest["id"], monto)

        # Resolve deuda_id by name
        deuda_id = accion.get("deuda_id")
        if mov_tipo == "pago_deuda" and not deuda_id and accion.get("nombre"):
            deudas = await self.repos["deuda"].get_all()
            nombre_lower = accion["nombre"].lower()
            for d in deudas:
                if nombre_lower in d["nombre"].lower():
                    deuda_id = d["id"]
                    break

        # Resolve cobro_id by name
        cobro_id = accion.get("cobro_id")
        if mov_tipo == "pago_cobro" and not cobro_id and accion.get("nombre"):
            cobro_repo = self.repos.get("cobro")
            if cobro_repo:
                cobros = await cobro_repo.get_by_deudor(accion["nombre"])
                if cobros:
                    cobro_id = cobros[0]["id"]

        mov_id = await mov_repo.create(
            tipo=mov_tipo,
            monto=monto,
            moneda=moneda,
            monto_cuenta=monto_cuenta,
            descripcion=accion.get("descripcion", ""),
            categoria=accion.get("categoria", "otros" if mov_tipo == "gasto" else None),
            comercio=accion.get("comercio"),
            metodo_pago=accion.get("metodo_pago"),
            fuente=accion.get("fuente", "texto"),
            cuenta_id=cuenta_id,
            cuenta_destino_id=cuenta_destino_id,
            tarjeta_id=tarjeta_id,
            tarjeta_periodo_id=tarjeta_periodo_id,
            deuda_id=deuda_id,
            cobro_id=cobro_id,
            cuotas=accion.get("cuotas", 0),
            monto_destino=monto_destino,
            fecha=fecha,
            mes=mes,
            semana=semana,
        )

        result = {"movimiento_id": mov_id}

        # Side effects by type
        if mov_tipo == "gasto" and self.budget:
            alerta = await self.budget.check_alert(accion.get("categoria", "otros"))
            if alerta:
                result["alert"] = alerta

        if mov_tipo == "gasto" and accion.get("cuotas", 0) > 1 and tarjeta_id and self.movimiento_cuota_repo:
            try:
                tarjeta_repo = self.repos.get("tarjeta")
                if tarjeta_repo:
                    tarjeta = await tarjeta_repo.get_by_id(tarjeta_id)
                    if tarjeta:
                        next_corte = tarjeta_repo.get_next_cuota_date(tarjeta)
                        await self.movimiento_cuota_repo.create_cuotas(
                            movimiento_id=mov_id,
                            cuotas_total=accion["cuotas"],
                            monto_total=monto,
                            tarjeta_id=tarjeta_id,
                            fecha_primera_cuota=next_corte,
                        )
            except Exception as e:
                logger.warning(f"Failed to generate cuotas: {e}")

        if mov_tipo == "pago_deuda" and deuda_id:
            await self.repos["deuda"].registrar_pago(
                deuda_id, monto, cuenta_id=cuenta_id, monto_cuenta=monto_cuenta
            )

        if mov_tipo == "pago_cobro" and cobro_id:
            cobro_repo = self.repos.get("cobro")
            if cobro_repo:
                updated = await cobro_repo.registrar_pago(
                    cobro_id, monto, cuenta_id=cuenta_id, monto_cuenta=monto_cuenta
                )
                result["data_response"] = f"Pago registrado. {updated.get('deudor', '')} debe ahora S/{updated.get('saldo_pendiente', 0):.2f}"

        return result

    async def _do_actualizar_movimiento(self, accion: dict) -> dict:
        mov_id = accion.get("movimiento_id")
        if not mov_id:
            return {}
        mov_repo = self.repos["movimiento"]
        old = await mov_repo.get_by_id(mov_id)
        if not old:
            return {"data_response": f"No encontre el movimiento #{mov_id}."}
        update_fields = {}
        for f in ("monto", "categoria", "descripcion", "comercio",
                  "metodo_pago", "cuenta_id", "tarjeta_id", "cuotas", "moneda"):
            if f in accion and accion[f] is not None:
                update_fields[f] = accion[f]
        fecha_dt = self._resolve_fecha(accion.get("fecha"))
        if fecha_dt:
            update_fields["fecha"] = fecha_dt.isoformat()
            update_fields["mes"] = fecha_dt.strftime("%Y-%m")
            update_fields["semana"] = fecha_dt.strftime("%Y-W%V")
        new_cuenta = accion.get("cuenta_id", old.get("cuenta_id"))
        new_monto = accion.get("monto", old["monto"])
        new_moneda = accion.get("moneda", old.get("moneda", "PEN"))
        if new_cuenta:
            update_fields["monto_cuenta"] = await self._convert_to_account_currency(
                new_monto, new_moneda, new_cuenta
            )
        if update_fields:
            await mov_repo.update(mov_id, **update_fields)
        return {"data_response": f"Movimiento #{mov_id} actualizado."}

    async def _do_eliminar_movimiento(self, accion: dict) -> dict:
        mov_id = accion.get("movimiento_id")
        if mov_id:
            await self._delete_movimiento(mov_id)
        return {}

    async def _do_eliminar_movimientos(self, accion: dict) -> dict:
        ids = accion.get("ids", [])
        for mid in ids:
            await self._delete_movimiento(mid)
        return {"data_response": f"Eliminados {len(ids)} movimientos."}

    async def _do_importar_estado_cuenta(self, accion: dict) -> dict:
        """Bulk import credit card statement lines."""
        lineas = accion.get("lineas", [])
        tarjeta_id = accion.get("tarjeta_id")
        if not lineas or not tarjeta_id:
            return {"data_response": "Faltan datos para importar."}

        mov_repo = self.repos["movimiento"]
        movimientos = []
        for linea in lineas:
            monto = linea.get("monto", 0)
            # Negative amounts = payments
            if monto < 0:
                mov_tipo = "pago_tarjeta"
                monto = abs(monto)
            else:
                mov_tipo = "gasto"

            # Parse fecha DD/MM/YYYY → YYYY-MM-DD
            fecha_raw = linea.get("fecha", "")
            try:
                if "/" in fecha_raw:
                    parts = fecha_raw.split("/")
                    if len(parts) == 3:
                        dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]),
                                      tzinfo=ZoneInfo(settings.timezone))
                        fecha = dt.isoformat()
                        mes = dt.strftime("%Y-%m")
                        semana = dt.strftime("%Y-W%V")
                    else:
                        raise ValueError
                else:
                    dt = datetime.fromisoformat(fecha_raw)
                    fecha = dt.isoformat()
                    mes = dt.strftime("%Y-%m")
                    semana = dt.strftime("%Y-W%V")
            except (ValueError, IndexError):
                now = datetime.now(ZoneInfo(settings.timezone))
                fecha = now.isoformat()
                mes = now.strftime("%Y-%m")
                semana = now.strftime("%Y-W%V")

            movimientos.append({
                "tipo": mov_tipo,
                "monto": monto,
                "moneda": linea.get("moneda", "PEN"),
                "descripcion": linea.get("descripcion", ""),
                "categoria": linea.get("categoria", "otros") if mov_tipo == "gasto" else None,
                "comercio": linea.get("comercio"),
                "tarjeta_id": tarjeta_id,
                "fuente": "importacion",
                "fecha": fecha,
                "mes": mes,
                "semana": semana,
            })

        ids = await mov_repo.bulk_create(movimientos)
        gastos = sum(1 for m in movimientos if m["tipo"] == "gasto")
        pagos = sum(1 for m in movimientos if m["tipo"] == "pago_tarjeta")
        return {"data_response": f"Importados {len(ids)} movimientos ({gastos} cargos, {pagos} pagos)."}

    # =========================================================================
    # Legacy adapters — convert old action format to unified movimiento
    # =========================================================================

    async def _do_legacy_gasto(self, accion: dict) -> dict:
        accion["mov_tipo"] = "gasto"
        result = await self._do_movimiento(accion)
        # Keep gasto_id for backward compatibility
        if result.get("movimiento_id"):
            result["gasto_id"] = result["movimiento_id"]
        return result

    async def _do_legacy_ingreso(self, accion: dict) -> dict:
        accion["mov_tipo"] = "ingreso"
        if accion.get("fuente") and not accion.get("descripcion"):
            accion["descripcion"] = accion["fuente"]
        return await self._do_movimiento(accion)

    async def _do_legacy_transferencia(self, accion: dict) -> dict:
        accion["mov_tipo"] = "transferencia"
        accion["cuenta_id"] = accion.get("cuenta_origen_id")
        return await self._do_movimiento(accion)

    async def _do_legacy_pago_tarjeta(self, accion: dict) -> dict:
        accion["mov_tipo"] = "pago_tarjeta"
        return await self._do_movimiento(accion)

    async def _do_legacy_pago_deuda(self, accion: dict) -> dict:
        accion["mov_tipo"] = "pago_deuda"
        return await self._do_movimiento(accion)

    async def _do_legacy_pago_cobro(self, accion: dict) -> dict:
        accion["mov_tipo"] = "pago_cobro"
        return await self._do_movimiento(accion)

    async def _do_legacy_actualizar_gasto(self, accion: dict) -> dict:
        accion["movimiento_id"] = accion.get("gasto_id")
        return await self._do_actualizar_movimiento(accion)

    async def _do_legacy_eliminar_gasto(self, accion: dict) -> dict:
        accion["movimiento_id"] = accion.get("gasto_id")
        return await self._do_eliminar_movimiento(accion)

    async def _do_legacy_eliminar_gastos(self, accion: dict) -> dict:
        return await self._do_eliminar_movimientos(accion)

    async def _do_legacy_eliminar_gastos_excepto(self, accion: dict) -> dict:
        periodo = accion.get("periodo", "hoy")
        conservar = set(accion.get("conservar_ids", []))
        mov_repo = self.repos["movimiento"]
        if periodo == "hoy":
            gastos = await mov_repo.get_gastos_hoy()
            to_delete = [g for g in gastos if g["id"] not in conservar]
            for g in to_delete:
                await self._delete_movimiento(g["id"])
            return {"data_response": f"Eliminados {len(to_delete)} gastos. Se conservaron {len(conservar)} gastos."}
        return {}

    async def _do_legacy_eliminar_gastos_periodo(self, accion: dict) -> dict:
        periodo = accion.get("periodo", "hoy")
        mov_repo = self.repos["movimiento"]
        if periodo == "hoy":
            gastos = await mov_repo.get_gastos_hoy()
            mantener = accion.get("mantener", 0)
            if mantener and mantener < len(gastos):
                keep_ids = {g["id"] for g in gastos[-mantener:]}
                to_delete = [g for g in gastos if g["id"] not in keep_ids]
            else:
                to_delete = gastos
            for g in to_delete:
                await self._delete_movimiento(g["id"])
            return {"data_response": f"Eliminados {len(to_delete)} gastos."}
        return {}

    async def _do_legacy_actualizar_ingreso(self, accion: dict) -> dict:
        accion["movimiento_id"] = accion.get("ingreso_id")
        return await self._do_actualizar_movimiento(accion)

    async def _do_legacy_eliminar_ingreso(self, accion: dict) -> dict:
        accion["movimiento_id"] = accion.get("ingreso_id")
        return await self._do_eliminar_movimiento(accion)

    # =========================================================================
    # Non-movimiento actions (unchanged logic)
    # =========================================================================

    async def _do_buscar_gasto(self, accion: dict) -> dict:
        texto = accion.get("texto", "")
        if not texto:
            return {}
        mov_repo = self.repos["movimiento"]
        gastos = await mov_repo.buscar(texto, tipo="gasto")
        if gastos:
            lines = [f"Encontre {len(gastos)} gastos:"]
            for g in gastos:
                desc = g.get("descripcion", "")
                comercio = f" en {g['comercio']}" if g.get("comercio") else ""
                metodo = f" ({g['metodo_pago']})" if g.get("metodo_pago") else ""
                fecha = g.get("fecha", "")[:10]
                cat = (g.get("categoria") or "otros").title()
                lines.append(f"  #{g['id']} | {fecha} {cat}: S/{g['monto']:.2f} {desc}{comercio}{metodo}")
            return {"data_response": "\n".join(lines)}
        return {"data_response": f"No encontre gastos con '{texto}'."}

    async def _do_consulta(self, accion: dict) -> dict:
        mov_repo = self.repos["movimiento"]
        periodo = accion.get("periodo", "hoy")
        if periodo == "hoy":
            return {"data_response": await self._resumen_hoy_detallado()}
        elif periodo == "semana":
            return {"data_response": await mov_repo.resumen_semana()}
        elif periodo == "mes":
            return {"data_response": await mov_repo.resumen_mes()}
        elif periodo == "deudas":
            return {"data_response": await self.repos["deuda"].resumen()}
        elif periodo == "cobros":
            cobro_repo = self.repos.get("cobro")
            if cobro_repo:
                return {"data_response": await cobro_repo.resumen()}
        elif periodo == "tarjetas":
            tarjeta_repo = self.repos.get("tarjeta")
            if tarjeta_repo:
                tarjetas = await tarjeta_repo.get_all()
                if tarjetas:
                    lines = ["Tus tarjetas:"]
                    for t in tarjetas:
                        usado = t.get("saldo_usado", 0) or 0
                        limite = t.get("limite_credito", 0) or 0
                        disponible = limite - usado
                        lines.append(
                            f"  | {t['nombre']} ({t['banco']}) *{t['ultimos_4']}"
                            f" - Limite: {t['moneda']} {limite:.2f}"
                            f", Usado: {usado:.2f}, Disponible: {disponible:.2f}"
                        )
                    return {"data_response": "\n".join(lines)}
                return {"data_response": "No tienes tarjetas registradas."}
        elif periodo == "cuentas":
            cuenta_repo = self.repos.get("cuenta")
            if cuenta_repo:
                cuentas = await cuenta_repo.get_all()
                if cuentas:
                    lines = ["Tus cuentas:"]
                    for c in cuentas:
                        lines.append(f"  | {c['nombre']} ({c['tipo']}): {c['moneda']} {c['saldo']:.2f}")
                    return {"data_response": "\n".join(lines)}
                return {"data_response": "No tienes cuentas registradas."}
        return {}

    async def _do_set_presupuesto(self, accion: dict) -> dict:
        presupuesto_repo = self.repos.get("presupuesto")
        categoria = accion.get("categoria", "")
        limite = accion.get("limite") or accion.get("limite_mensual", 0)
        if presupuesto_repo and categoria and limite:
            await presupuesto_repo.save({
                "categoria": categoria,
                "limite_mensual": limite,
                "alerta_porcentaje": accion.get("alerta_porcentaje", 80),
            })
            return {"data_response": f"Presupuesto de {categoria}: S/{float(limite):.2f}/mes"}
        return {}

    async def _do_agregar_deuda(self, accion: dict) -> dict:
        await self.repos["deuda"].save({
            "nombre": accion["nombre"],
            "saldo_actual": accion.get("saldo", 0),
            "entidad": accion.get("entidad"),
            "cuotas_total": accion.get("cuotas_total", 0),
            "cuotas_pagadas": accion.get("cuotas_pagadas", 0),
            "cuota_monto": accion.get("cuota_monto", 0),
            "tasa_interes_mensual": accion.get("tasa", 0),
            "pago_minimo": accion.get("pago_minimo", 0),
        })
        return {}

    async def _do_set_perfil(self, accion: dict) -> dict:
        perfil_repo = self.repos.get("perfil")
        if perfil_repo:
            update_data = {}
            if accion.get("nombre"):
                update_data["nombre"] = accion["nombre"]
            if accion.get("moneda_default"):
                update_data["moneda_default"] = accion["moneda_default"]
            if accion.get("onboarding_completo"):
                update_data["onboarding_completo"] = 1
            if update_data:
                await perfil_repo.create_or_update(update_data)
        return {}

    async def _do_crear_cuenta(self, accion: dict) -> dict:
        cuenta_repo = self.repos.get("cuenta")
        if cuenta_repo:
            await cuenta_repo.save({
                "nombre": accion["nombre"],
                "tipo": accion.get("tipo_cuenta", "efectivo"),
                "moneda": accion.get("moneda", "PEN"),
                "saldo_inicial": accion.get("saldo_inicial", accion.get("saldo", 0)),
                "metodos_pago": accion.get("metodos_pago", []),
            })
        return {}

    async def _do_actualizar_cuenta(self, accion: dict) -> dict:
        cuenta_repo = self.repos.get("cuenta")
        if not cuenta_repo:
            return {}
        cuenta_id = accion.get("cuenta_id")
        if not cuenta_id:
            return {"data_response": "Necesito el ID de la cuenta para editarla."}
        existing = await cuenta_repo.get_by_id(cuenta_id)
        if not existing:
            return {"data_response": f"No encontre la cuenta #{cuenta_id}."}
        update_data = {"id": cuenta_id}
        update_data["nombre"] = accion.get("nombre", existing["nombre"])
        update_data["tipo"] = accion.get("tipo_cuenta", existing["tipo"])
        update_data["moneda"] = accion.get("moneda", existing["moneda"])
        update_data["saldo_inicial"] = accion.get("saldo_inicial", existing.get("saldo_inicial", 0))
        update_data["metodos_pago"] = accion.get("metodos_pago", existing.get("metodos_pago", []))
        await cuenta_repo.save(update_data)
        return {"data_response": f"Cuenta #{cuenta_id} actualizada."}

    async def _do_consulta_cambio(self, accion: dict) -> dict:
        monto = accion.get("monto", 1.0)
        de = accion.get("de", "USD")
        a = accion.get("a", "PEN")
        converted = await self.currency.convert(monto, de, a)
        rate = await self.currency.get_rate(de, a)
        return {"data_response": f"{de} {monto:.2f} = {a} {converted:.2f} (tasa: 1 {de} = {rate:.4f} {a})"}

    async def _do_tool(self, accion: dict) -> dict:
        tool_name = accion.get("name", "")
        params = accion.get("params", {})
        # Try built-in tools first
        tool_result = self.tools.execute(tool_name, params)
        if tool_result.startswith("Error: Unknown tool"):
            # Try plugin tools
            self.plugins.reload_all()
            plugin_handler = self.plugins.get_tool_handler(tool_name)
            if plugin_handler:
                try:
                    tool_result = plugin_handler(params)
                except Exception as e:
                    tool_result = f"Plugin tool error: {e}"
        return {"data_response": tool_result}

    async def _do_cobro(self, accion: dict) -> dict:
        cobro_repo = self.repos.get("cobro")
        if cobro_repo:
            await cobro_repo.save({
                "deudor": accion["deudor"],
                "concepto": accion.get("concepto", ""),
                "monto_total": accion["monto"],
                "moneda": accion.get("moneda", "PEN"),
            })
        return {}

    async def _do_consulta_consumo(self, accion: dict) -> dict:
        """Query energy consumption data for a specific time range."""
        consumo_repo = self.repos.get("consumo")
        if not consumo_repo:
            return {"data_response": "No hay datos de consumo disponibles."}

        desde = accion.get("desde", "")
        hasta = accion.get("hasta", "")
        agrupacion = accion.get("agrupacion", "hora")  # minuto|hora|dia

        slice_hours = {"minuto": 0, "hora": 1, "dia": 24}.get(agrupacion, 1)

        try:
            data = await consumo_repo.get_chart_data("luz", desde, hasta, slice_hours)
            if not data:
                return {"data_response": f"Sin lecturas de consumo entre {desde} y {hasta}."}

            lines = []
            total_kwh = 0
            max_power = 0
            min_power = float('inf')
            sum_power = 0

            for d in data:
                pw = d.get("power_w") or 0
                sum_power += pw
                if pw > max_power:
                    max_power = pw
                if pw < min_power and pw > 0:
                    min_power = pw
                hora = (d.get("fecha") or "")
                if agrupacion == "minuto":
                    hora = hora[11:16] if len(hora) >= 16 else hora
                elif agrupacion == "hora":
                    hora = hora[11:13] + "h" if len(hora) >= 13 else hora
                lines.append(f"  {hora}: {pw:.0f}W | {d.get('current_a', 0):.2f}A | {d.get('voltage_v', 0):.1f}V")

            avg_power = sum_power / len(data) if data else 0

            # Limit detail lines for readability
            if len(lines) > 30:
                step = len(lines) // 25
                lines = lines[::step]

            result = f"Consumo {desde} a {hasta} ({len(data)} lecturas):\n"
            result += f"  Promedio: {avg_power:.0f}W | Pico: {max_power:.0f}W | Min: {min_power:.0f}W\n"
            result += "Detalle:\n" + "\n".join(lines)
            return {"data_response": result}
        except Exception as e:
            logger.error(f"Error in consulta_consumo: {e}")
            return {"data_response": f"Error consultando consumo: {e}"}

    async def _do_tipo_cambio_sunat(self, accion: dict) -> dict:
        tc = await self.sunat.get_tipo_cambio()
        return {"data_response": f"Tipo de cambio SUNAT ({tc['fuente']}):\nCompra: S/{tc['compra']}\nVenta: S/{tc['venta']}"}

    async def _do_tarjeta(self, accion: dict) -> dict:
        tarjeta_repo = self.repos.get("tarjeta")
        if tarjeta_repo:
            await tarjeta_repo.save({
                "nombre": accion["nombre"],
                "banco": accion.get("banco", ""),
                "tipo": accion.get("tipo_tarjeta", "credito"),
                "ultimos_4": accion.get("ultimos_4", ""),
                "limite_credito": accion.get("limite_credito", 0),
                "fecha_corte": accion.get("fecha_corte", 1),
                "fecha_pago": accion.get("fecha_pago", 15),
            })
        return {}

    async def _do_memorizar(self, accion: dict) -> dict:
        memoria_repo = self.repos.get("memoria")
        if memoria_repo:
            await memoria_repo.save(
                categoria=accion.get("categoria", "dato"),
                clave=accion.get("clave", ""),
                valor=accion.get("valor", ""),
            )
            logger.info(f"Memorized: [{accion.get('categoria')}] {accion.get('clave')}")
        return {}

    async def _do_recordatorio(self, accion: dict) -> dict:
        recordatorio_repo = self.repos.get("recordatorio")
        if not recordatorio_repo:
            return {}
        mensaje = accion.get("mensaje", "")
        hora = accion.get("hora", "09:00")
        dias = accion.get("dias", "todos")
        rec_id = await recordatorio_repo.save(mensaje=mensaje, hora=hora, dias=dias)
        logger.info(f"Recordatorio #{rec_id} saved: {mensaje} @ {hora} ({dias})")

        # Sync to Google Calendar
        google_svc = self.repos.get("google_service")
        cal_note = ""
        if google_svc:
            event_id = google_svc.create_calendar_event(mensaje, hora, dias)
            if event_id:
                await recordatorio_repo.update_google_event_id(rec_id, event_id)
                cal_note = " (sincronizado con Google Calendar)"
                logger.info(f"Recordatorio #{rec_id} synced to Calendar: {event_id}")
            else:
                logger.warning(f"Recordatorio #{rec_id} Calendar sync failed")
        else:
            logger.warning("google_service not found in repos, skipping Calendar sync")

        return {"data_response": f"Recordatorio #{rec_id} creado{cal_note}."}

    async def _resumen_hoy_detallado(self) -> str:
        mov_repo = self.repos["movimiento"]
        gastos = await mov_repo.get_gastos_hoy()
        if not gastos:
            return "Hoy no has registrado gastos."
        gastos.sort(key=lambda g: g["id"])
        total = sum(g["monto"] for g in gastos)
        lines = [f"Gastos de hoy ({len(gastos)}):"]
        for g in gastos:
            desc = g.get("descripcion", "")
            comercio = f" en {g['comercio']}" if g.get("comercio") else ""
            metodo = f" ({g['metodo_pago']})" if g.get("metodo_pago") else ""
            fuente = f" [via {g['fuente']}]" if g.get("fuente") and g["fuente"] != "texto" else ""
            cat = (g.get("categoria") or "otros").title()
            lines.append(f"  #{g['id']} | {cat}: S/{g['monto']:.2f} {desc}{comercio}{metodo}{fuente}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)
