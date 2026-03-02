import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {"PEN": "S/", "USD": "$", "EUR": "€"}


class SchedulerService:
    def __init__(self, message_bus, gasto_repo, presupuesto_repo=None,
                 budget_service=None, perfil_repo=None, cobro_repo=None,
                 tarjeta_repo=None,
                 sunat_service=None, tipo_cambio_repo=None,
                 timezone: str = "America/Lima",
                 movimiento_repo=None, tarjeta_periodo_repo=None,
                 sonoff_service=None, consumo_repo=None,
                 mcp_manager=None,
                 trading_bot=None,
                 llm_client=None):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.bus = message_bus
        self.gasto_repo = gasto_repo
        self.presupuesto_repo = presupuesto_repo
        self.budget_service = budget_service
        self.perfil_repo = perfil_repo
        self.cobro_repo = cobro_repo
        self.tarjeta_repo = tarjeta_repo
        self.sunat_service = sunat_service
        self.tipo_cambio_repo = tipo_cambio_repo
        self.movimiento_repo = movimiento_repo
        self.tarjeta_periodo_repo = tarjeta_periodo_repo
        self.sonoff_service = sonoff_service
        self.consumo_repo = consumo_repo
        self.mcp_manager = mcp_manager
        self.trading_bot = trading_bot
        self.llm_client = llm_client

    async def _get_user_name(self) -> str:
        if self.perfil_repo:
            try:
                perfil = await self.perfil_repo.get()
                if perfil and perfil.get("nombre"):
                    return perfil["nombre"]
            except Exception:
                pass
        return ""

    async def _get_currency_symbol(self) -> str:
        if self.perfil_repo:
            try:
                perfil = await self.perfil_repo.get()
                if perfil and perfil.get("moneda_default"):
                    return CURRENCY_SYMBOLS.get(perfil["moneda_default"], "S/")
            except Exception:
                pass
        return "S/"

    def start(self):
        # Morning greeting at 8:00 AM
        self.scheduler.add_job(
            self._saludo_manana,
            "cron",
            hour=8,
            minute=0,
            id="saludo_manana",
        )

        # Daily expense check at 8:00 PM - proactive question
        self.scheduler.add_job(
            self._pregunta_gastos_diarios,
            "cron",
            hour=20,
            minute=0,
            id="pregunta_gastos",
        )

        # Weekly summary Friday at 8:00 PM
        self.scheduler.add_job(
            self._resumen_semanal,
            "cron",
            day_of_week="fri",
            hour=20,
            minute=30,
            id="resumen_semanal",
        )

        # Monthly summary on 1st at 9:00 AM
        self.scheduler.add_job(
            self._resumen_mensual,
            "cron",
            day=1,
            hour=9,
            minute=0,
            id="resumen_mensual",
        )

        # Budget alerts every 2 hours
        if self.budget_service and self.presupuesto_repo:
            self.scheduler.add_job(
                self._alerta_presupuestos,
                "interval",
                hours=2,
                id="alerta_presupuestos",
            )

        # Cobros/debt reminders at 10 AM
        if self.cobro_repo:
            self.scheduler.add_job(
                self._recordatorio_cobros,
                "cron",
                hour=10,
                minute=0,
                id="recordatorio_cobros",
            )

        # Inactivity nudge at 9 PM
        self.scheduler.add_job(
            self._alerta_inactividad,
            "cron",
            hour=21,
            minute=0,
            id="alerta_inactividad",
        )

        # Daily exchange rate persistence at 10:30 AM
        if self.sunat_service:
            self.scheduler.add_job(
                self._persistir_tipo_cambio,
                "cron",
                hour=10,
                minute=30,
                id="tipo_cambio_diario",
            )

        # Credit card payment alerts at 9:30 AM
        if self.tarjeta_repo:
            self.scheduler.add_job(
                self._alerta_pago_tarjeta,
                "cron",
                hour=9,
                minute=30,
                id="alerta_pago_tarjeta",
            )

        # Calendar events check - every minute via MCP
        if self.mcp_manager:
            self.scheduler.add_job(
                self._check_calendar_events,
                "cron",
                minute="*",
                id="check_calendar_events",
            )
        self._calendar_events_notified = set()  # track already-notified event IDs

        # Sonoff 5-minute reading save
        if self.sonoff_service and self.consumo_repo:
            self.scheduler.add_job(
                self._guardar_lectura_sonoff,
                "interval",
                minutes=1,
                id="sonoff_1min",
            )

        # Facturar periodos de tarjeta at 00:30 daily
        if self.tarjeta_periodo_repo and self.tarjeta_repo:
            self.scheduler.add_job(
                self._facturar_periodos,
                "cron",
                hour=0,
                minute=30,
                id="facturar_periodos",
            )

        # Trading bot — run every minute + Darwin every hour
        if self.trading_bot:
            self.scheduler.add_job(
                self._trading_cycle,
                "interval",
                minutes=1,
                id="trading_cycle",
            )
            self.scheduler.add_job(
                self._trading_darwin,
                "cron",
                minute=0,
                id="trading_darwin",
            )

        self.scheduler.start()
        jobs = [j.id for j in self.scheduler.get_jobs()]
        logger.info(f"Scheduler started with jobs: {jobs}")

    def _get_mov_or_gasto_repo(self):
        """Prefer movimiento_repo, fallback to gasto_repo."""
        return self.movimiento_repo or self.gasto_repo

    # --- Morning greeting ---
    async def _saludo_manana(self):
        nombre = await self._get_user_name()
        saludo = f"Buenos dias {nombre}!" if nombre else "Buenos dias!"
        msg = f"{saludo} Nuevo dia, recuerda registrar tus gastos. Si necesitas algo, aqui estoy."
        await self.bus.send_proactive(msg)

    # --- 8 PM: Proactive daily expense question ---
    async def _pregunta_gastos_diarios(self):
        nombre = await self._get_user_name()
        sym = await self._get_currency_symbol()
        epa = f"Epa {nombre}!" if nombre else "Epa!"

        try:
            repo = self._get_mov_or_gasto_repo()
            gastos = await (repo.get_gastos_hoy() if hasattr(repo, 'get_gastos_hoy') else repo.get_today())
            total = sum(g["monto"] for g in gastos)
        except Exception:
            gastos = []
            total = 0

        if gastos:
            # Has some expenses, ask if there's more
            cats = {}
            for g in gastos:
                cat = g.get("categoria", "otros")
                cats[cat] = cats.get(cat, 0) + g["monto"]
            cat_text = ", ".join(f"{c}: {sym}{m:.2f}" for c, m in cats.items())
            msg = (
                f"{epa} Hoy llevas {sym}{total:.2f} en gastos ({cat_text}). "
                f"Te falto registrar algo? Movilidad, almuerzo, cafe, compras?"
            )
        else:
            # No expenses at all
            msg = (
                f"{epa} No registraste ningun gasto hoy. "
                f"Cuanto gastaste en movilidad? Almorzaste fuera? Algun cafe o compra? "
                f"Cuentame y lo registro."
            )

        await self.bus.send_proactive(msg)

    # --- Cobros reminders ---
    async def _recordatorio_cobros(self):
        if not self.cobro_repo:
            return
        try:
            cobros = await self.cobro_repo.get_all(solo_pendientes=True)
            if not cobros:
                return

            nombre = await self._get_user_name()
            sym = await self._get_currency_symbol()
            lines = []
            total = 0

            for c in cobros:
                deudor = c["deudor"]
                saldo = c["saldo_pendiente"]
                concepto = c.get("concepto", "")
                concepto_text = f" ({concepto})" if concepto else ""
                lines.append(f"  - {deudor} te debe {sym}{saldo:.2f}{concepto_text}")
                total += saldo

            if lines:
                saludo = f"Hey {nombre}," if nombre else "Hey,"
                msg = (
                    f"{saludo} recordatorio de cuentas por cobrar:\n"
                    + "\n".join(lines)
                    + f"\n  Total pendiente: {sym}{total:.2f}"
                    + "\nYa te pagaron algo? Cuentame para actualizarlo."
                )
                await self.bus.send_proactive(msg)

        except Exception as e:
            logger.error(f"Error checking cobros: {e}")

    # --- Weekly summary ---
    async def _resumen_semanal(self):
        nombre = await self._get_user_name()
        saludo = f"Hey {nombre}," if nombre else "Hey,"
        repo = self._get_mov_or_gasto_repo()
        text = await repo.resumen_semana()
        await self.bus.send_proactive(f"{saludo} resumen semanal:\n{text}")

    # --- Monthly summary ---
    async def _resumen_mensual(self):
        nombre = await self._get_user_name()
        saludo = f"Hola {nombre}!" if nombre else "Hola!"
        repo = self._get_mov_or_gasto_repo()
        text = await repo.resumen_mes()
        await self.bus.send_proactive(f"{saludo} Resumen del mes anterior:\n{text}")

    # --- Budget alerts ---
    async def _alerta_presupuestos(self):
        try:
            presupuestos = await self.presupuesto_repo.get_all()
            alertas = []
            for p in presupuestos:
                alerta = await self.budget_service.check_alert(p["categoria"])
                if alerta:
                    alertas.append(alerta)
            if alertas:
                msg = "Alerta de presupuestos:\n" + "\n".join(alertas)
                await self.bus.send_proactive(msg)
        except Exception as e:
            logger.error(f"Error checking budget alerts: {e}")

    # --- 9 PM inactivity nudge ---
    async def _alerta_inactividad(self):
        try:
            repo = self._get_mov_or_gasto_repo()
            gastos = await (repo.get_gastos_hoy() if hasattr(repo, 'get_gastos_hoy') else repo.get_today())
            if not gastos:
                nombre = await self._get_user_name()
                if nombre:
                    msg = f"{nombre}, se acaba el dia y no registraste gastos. Seguro no gastaste nada hoy? Ni movilidad o comida?"
                else:
                    msg = "Se acaba el dia y no registraste gastos. Seguro no gastaste nada hoy?"
                await self.bus.send_proactive(msg)
        except Exception as e:
            logger.error(f"Error checking inactivity: {e}")

    # --- Calendar events check via MCP ---
    async def _check_calendar_events(self):
        if not self.mcp_manager or not self.mcp_manager.has_tool("get_events"):
            return
        try:
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo
            import re

            now = datetime.now(ZoneInfo(self.scheduler.timezone.key))
            time_min = now.replace(second=0, microsecond=0).isoformat()
            time_max = (now.replace(second=0, microsecond=0) + timedelta(minutes=1)).isoformat()

            result = await self.mcp_manager.call_tool("get_events", {
                "user_google_email": "snestors@gmail.com",
                "time_min": time_min,
                "time_max": time_max,
            })
            if not result or "no events found" in str(result).lower():
                return

            result_str = str(result)

            # Extract event IDs and summaries from MCP text response
            # Format: "Event Name" (Starts: ...) ID: abc123 | Link: ...
            event_ids = re.findall(r'ID:\s*(\S+)', result_str)
            summaries = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]\s*\(Starts:', result_str)

            if not event_ids:
                return

            nombre = await self._get_user_name()
            prefix = f"{nombre}, " if nombre else ""

            for i, eid in enumerate(event_ids):
                eid = eid.rstrip('|').strip()
                if eid in self._calendar_events_notified:
                    continue
                self._calendar_events_notified.add(eid)
                summary = summaries[i] if i < len(summaries) else "Evento de calendario"
                await self.bus.send_proactive(f"{prefix}recordatorio: {summary}")

            # Purge set if it grows too large (events from past days)
            if len(self._calendar_events_notified) > 200:
                self._calendar_events_notified.clear()

        except Exception as e:
            logger.error(f"Error checking calendar events: {e}")

    # --- Daily exchange rate persistence ---
    async def _persistir_tipo_cambio(self):
        if not self.sunat_service:
            return
        try:
            await self.sunat_service.get_tipo_cambio()
            logger.info("Daily exchange rate persisted")
        except Exception as e:
            logger.error(f"Error persisting exchange rate: {e}")

    # --- Credit card payment alerts ---
    async def _alerta_pago_tarjeta(self):
        if not self.tarjeta_repo:
            return
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo(self.scheduler.timezone.key)).date()
            tarjetas = await self.tarjeta_repo.get_all()
            alertas = []
            for t in tarjetas:
                if t.get("tipo") != "credito":
                    continue
                period = self.tarjeta_repo.get_billing_period(t, today)
                from datetime import date
                fecha_pago = date.fromisoformat(period["fecha_pago"])
                dias_para_pago = (fecha_pago - today).days
                usado = t.get("saldo_usado", 0) or 0
                if usado <= 0:
                    continue
                if dias_para_pago == 3:
                    alertas.append(f"  - {t['nombre']} (*{t['ultimos_4']}): pago en 3 dias (dia {fecha_pago.day}), saldo S/{usado:.2f}")
                elif dias_para_pago == 0:
                    alertas.append(f"  - {t['nombre']} (*{t['ultimos_4']}): HOY vence el pago, saldo S/{usado:.2f}")

            if alertas:
                nombre = await self._get_user_name()
                prefix = f"{nombre}, " if nombre else ""
                msg = f"{prefix}alerta de tarjetas de credito:\n" + "\n".join(alertas)
                await self.bus.send_proactive(msg)
        except Exception as e:
            logger.error(f"Error checking tarjeta payments: {e}")

    # --- Facturar periodos de tarjeta ---
    async def _facturar_periodos(self):
        """Close billing periods on their corte day. Runs daily at 00:30."""
        if not self.tarjeta_periodo_repo or not self.tarjeta_repo or not self.movimiento_repo:
            return
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo(self.scheduler.timezone.key)).date()
            dia_hoy = today.day

            # Find open periods whose tarjeta has fecha_corte == today
            periodos = await self.tarjeta_periodo_repo.get_abiertos_para_facturar(dia_hoy)
            for p in periodos:
                tarjeta_id = p["tarjeta_id"]
                # Sum all gastos in this period
                from src.database.db import get_db
                db = await get_db()
                cursor = await db.execute(
                    """SELECT COALESCE(SUM(monto), 0) FROM movimientos
                       WHERE tarjeta_id = ? AND tipo = 'gasto'
                       AND fecha >= ? AND fecha <= ?""",
                    (tarjeta_id, p["fecha_inicio"], p["fecha_fin"]),
                )
                total = (await cursor.fetchone())[0]
                await self.tarjeta_periodo_repo.facturar(p["id"], total)
                logger.info(f"Facturado periodo {p['periodo']} tarjeta #{tarjeta_id}: {total}")
        except Exception as e:
            logger.error(f"Error facturando periodos: {e}")

    # --- Sonoff 5-minute reading ---
    async def _guardar_lectura_sonoff(self):
        if not self.sonoff_service or not self.consumo_repo:
            return
        try:
            data = self.sonoff_service.latest
            if data:
                await self.consumo_repo.save_5min_sonoff(
                    power_w=data.get("power_w", 0),
                    voltage_v=data.get("voltage_v", 0),
                    current_a=data.get("current_a", 0),
                    day_kwh=data.get("day_kwh", 0),
                    month_kwh=data.get("month_kwh", 0),
                )
        except Exception as e:
            logger.error(f"Error saving Sonoff reading: {e}")

    # --- Trading bot cycle (every minute) ---
    async def _trading_cycle(self):
        if not self.trading_bot:
            return
        try:
            result = await self.trading_bot.run_with_sentinel(llm=self.llm_client)
            action = result.get("action", "")
            mode = "PAPER" if self.trading_bot.exchange.paper_mode else "REAL"

            # Proactive alerts for opens/closes
            if action == "opened":
                pair = result.get("pair", "?")
                side = result.get("side", "?").upper()
                price = result.get("price", 0)
                strategy = result.get("strategy", "?")
                score = result.get("score", 0)
                await self.bus.send_proactive(
                    f"[Trading {mode}] {side} {pair} @ {price:.4f} "
                    f"(score={score}, {strategy})"
                )

            elif action == "closed":
                trade = result.get("trade", {})
                pair = trade.get("pair", "?")
                pnl = trade.get("pnl", 0)
                reason = trade.get("reason", "?")
                emoji = "+" if pnl > 0 else ""
                await self.bus.send_proactive(
                    f"[Trading {mode}] Cerrado {pair}: {emoji}${pnl:.4f} ({reason})"
                )

            # Sentinel alerts
            elif action == "sentinel_tighten":
                pair = result.get("pair", "?")
                old_sl = result.get("old_sl", 0)
                new_sl = result.get("new_sl", 0)
                reason = result.get("reason", "")
                await self.bus.send_proactive(
                    f"[Sentinel {mode}] TIGHTEN {pair}: SL {old_sl:.6f} → {new_sl:.6f}\n{reason}"
                )

            elif action == "sentinel_close":
                # Already handled by "closed" above (reason=sentinel_close)
                pass

            elif action == "sentinel_let_run":
                pair = result.get("pair", "?")
                trigger = result.get("new_trailing_trigger", 0)
                reason = result.get("reason", "")
                await self.bus.send_proactive(
                    f"[Sentinel {mode}] LET_RUN {pair}: trailing trigger → {trigger:.2f}%\n{reason}"
                )

            elif action == "pretrade_blocked":
                pair = result.get("pair", "?")
                direction = result.get("direction", "?")
                score = result.get("score", 0)
                reason = result.get("reason", "")
                await self.bus.send_proactive(
                    f"[Pre-trade {mode}] BLOCKED {direction} {pair} (score={score})\n{reason}"
                )

        except Exception as e:
            logger.error(f"Trading cycle error: {e}", exc_info=True)

    # --- Darwin evolution (every hour) ---
    async def _trading_darwin(self):
        if not self.trading_bot:
            return
        try:
            from trading.darwin import darwin_cycle
            self.trading_bot._ensure_loaded()
            changes = await darwin_cycle(
                self.trading_bot.brain,
                self.trading_bot.journal,
                llm=self.llm_client,
                context=self.trading_bot.context,
            )
            if changes:
                msg = "[Darwin Opus]\n" + "\n".join(f"• {c}" for c in changes)
                await self.bus.send_proactive(msg)
        except Exception as e:
            logger.error(f"Darwin cycle error: {e}", exc_info=True)

    def stop(self):
        self.scheduler.shutdown()
