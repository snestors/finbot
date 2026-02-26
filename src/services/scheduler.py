import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {"PEN": "S/", "USD": "$", "EUR": "€"}


class SchedulerService:
    def __init__(self, message_bus, gasto_repo, presupuesto_repo=None,
                 budget_service=None, perfil_repo=None, timezone: str = "America/Lima"):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.bus = message_bus
        self.gasto_repo = gasto_repo
        self.presupuesto_repo = presupuesto_repo
        self.budget_service = budget_service
        self.perfil_repo = perfil_repo

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
        # Daily summary at 8:00 AM
        self.scheduler.add_job(
            self._resumen_diario,
            "cron",
            hour=8,
            minute=0,
            id="resumen_diario",
        )

        # Weekly summary Friday at 8:00 PM
        self.scheduler.add_job(
            self._resumen_semanal,
            "cron",
            day_of_week="fri",
            hour=20,
            minute=0,
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

        # Inactivity alert at 9 PM
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

    async def _resumen_diario(self):
        nombre = await self._get_user_name()
        saludo = f"Buenos dias {nombre}!" if nombre else "Buenos dias!"
        text = await self.gasto_repo.resumen_hoy()
        await self.bus.send_proactive(f"{saludo} {text}")

    async def _resumen_semanal(self):
        nombre = await self._get_user_name()
        saludo = f"Hey {nombre}," if nombre else "Hey,"
        text = await self.gasto_repo.resumen_semana()
        await self.bus.send_proactive(f"{saludo} resumen semanal:\n{text}")

    async def _resumen_mensual(self):
        nombre = await self._get_user_name()
        saludo = f"Hola {nombre}!" if nombre else "Hola!"
        text = await self.gasto_repo.resumen_mes()
        await self.bus.send_proactive(f"{saludo} Resumen del mes anterior:\n{text}")

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

    async def _alerta_inactividad(self):
        try:
            gastos = await self.gasto_repo.get_today()
            if not gastos:
                nombre = await self._get_user_name()
                saludo = f"{nombre}, n" if nombre else "N"
                await self.bus.send_proactive(
                    f"{saludo}o registraste gastos hoy. Si tuviste alguno, aun puedes anotarlo!"
                )
        except Exception as e:
            logger.error(f"Error checking inactivity: {e}")

    def stop(self):
        self.scheduler.shutdown()
