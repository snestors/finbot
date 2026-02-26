import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {"PEN": "S/", "USD": "$", "EUR": "€"}


class SchedulerService:
    def __init__(self, message_bus, gasto_repo, presupuesto_repo=None,
                 budget_service=None, perfil_repo=None, cobro_repo=None,
                 timezone: str = "America/Lima"):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.bus = message_bus
        self.gasto_repo = gasto_repo
        self.presupuesto_repo = presupuesto_repo
        self.budget_service = budget_service
        self.perfil_repo = perfil_repo
        self.cobro_repo = cobro_repo

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

        self.scheduler.start()
        jobs = [j.id for j in self.scheduler.get_jobs()]
        logger.info(f"Scheduler started with jobs: {jobs}")

    # --- Morning greeting ---
    async def _saludo_manana(self):
        nombre = await self._get_user_name()
        sym = await self._get_currency_symbol()
        saludo = f"Buenos dias {nombre}!" if nombre else "Buenos dias!"

        try:
            gastos_ayer = await self.gasto_repo.resumen_hoy()  # yesterday context
        except Exception:
            gastos_ayer = ""

        msg = f"{saludo} Nuevo dia, recuerda registrar tus gastos. Si necesitas algo, aqui estoy."
        await self.bus.send_proactive(msg)

    # --- 8 PM: Proactive daily expense question ---
    async def _pregunta_gastos_diarios(self):
        nombre = await self._get_user_name()
        sym = await self._get_currency_symbol()
        epa = f"Epa {nombre}!" if nombre else "Epa!"

        try:
            gastos = await self.gasto_repo.get_today()
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
        text = await self.gasto_repo.resumen_semana()
        await self.bus.send_proactive(f"{saludo} resumen semanal:\n{text}")

    # --- Monthly summary ---
    async def _resumen_mensual(self):
        nombre = await self._get_user_name()
        saludo = f"Hola {nombre}!" if nombre else "Hola!"
        text = await self.gasto_repo.resumen_mes()
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
            gastos = await self.gasto_repo.get_today()
            if not gastos:
                nombre = await self._get_user_name()
                if nombre:
                    msg = f"{nombre}, se acaba el dia y no registraste gastos. Seguro no gastaste nada hoy? Ni movilidad o comida?"
                else:
                    msg = "Se acaba el dia y no registraste gastos. Seguro no gastaste nada hoy?"
                await self.bus.send_proactive(msg)
        except Exception as e:
            logger.error(f"Error checking inactivity: {e}")

    def stop(self):
        self.scheduler.shutdown()
