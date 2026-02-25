from src.repository.presupuesto_repo import PresupuestoRepo
from src.repository.gasto_repo import GastoRepo


class BudgetService:
    def __init__(self, presupuesto_repo: PresupuestoRepo, gasto_repo: GastoRepo):
        self.presupuesto_repo = presupuesto_repo
        self.gasto_repo = gasto_repo

    async def check_alert(self, categoria: str) -> str | None:
        presupuesto = await self.presupuesto_repo.get_by_categoria(categoria)
        if not presupuesto:
            return None

        total = await self.gasto_repo.total_categoria_mes(categoria)
        limite = presupuesto["limite_mensual"]
        porcentaje = (total / limite * 100) if limite > 0 else 0
        alerta_pct = presupuesto.get("alerta_porcentaje", 80)

        if porcentaje >= 100:
            return f"{categoria.title()}: S/{total:.2f} / S/{limite:.2f} ({porcentaje:.0f}%) - EXCEDIDO!"
        elif porcentaje >= alerta_pct:
            return f"{categoria.title()}: S/{total:.2f} / S/{limite:.2f} ({porcentaje:.0f}%)"
        return None

    async def check_alerts_batch(self, items: list[dict]) -> list[str]:
        categorias_vistas = set()
        alertas = []
        for item in items:
            cat = item.get("categoria", "")
            if cat and cat not in categorias_vistas:
                categorias_vistas.add(cat)
                alerta = await self.check_alert(cat)
                if alerta:
                    alertas.append(alerta)
        return alertas
