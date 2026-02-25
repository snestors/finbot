import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, message_bus, gasto_repo, presupuesto_repo=None,
                 budget_service=None, timezone: str = "America/Lima"):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.bus = message_bus
        self.gasto_repo = gasto_repo
        self.presupuesto_repo = presupuesto_repo
        self.budget_service = budget_service

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
        text = await self.gasto_repo.resumen_hoy()
        await self.bus.send_proactive(f"Buenos dias! {text}")

    async def _resumen_semanal(self):
        text = await self.gasto_repo.resumen_semana()
        await self.bus.send_proactive(f"Resumen semanal:\n{text}")

    async def _resumen_mensual(self):
        text = await self.gasto_repo.resumen_mes()
        await self.bus.send_proactive(f"Resumen del mes anterior:\n{text}")

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
                await self.bus.send_proactive(
                    "No registraste gastos hoy. Si tuviste alguno, aun puedes anotarlo!"
                )
        except Exception as e:
            logger.error(f"Error checking inactivity: {e}")

    def stop(self):
        self.scheduler.shutdown()
