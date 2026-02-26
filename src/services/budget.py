from src.repository.presupuesto_repo import PresupuestoRepo
from src.repository.gasto_repo import GastoRepo

CURRENCY_SYMBOLS = {"PEN": "S/", "USD": "$", "EUR": "€"}


class BudgetService:
    def __init__(self, presupuesto_repo: PresupuestoRepo, gasto_repo: GastoRepo,
                 perfil_repo=None):
        self.presupuesto_repo = presupuesto_repo
        self.gasto_repo = gasto_repo
        self.perfil_repo = perfil_repo

    async def _get_symbol(self) -> str:
        if self.perfil_repo:
            try:
                perfil = await self.perfil_repo.get()
                if perfil and perfil.get("moneda_default"):
                    return CURRENCY_SYMBOLS.get(perfil["moneda_default"], "S/")
            except Exception:
                pass
        return "S/"

    async def check_alert(self, categoria: str) -> str | None:
        presupuesto = await self.presupuesto_repo.get_by_categoria(categoria)
        if not presupuesto:
            return None

        total = await self.gasto_repo.total_categoria_mes(categoria)
        limite = presupuesto["limite_mensual"]
        porcentaje = (total / limite * 100) if limite > 0 else 0
        alerta_pct = presupuesto.get("alerta_porcentaje", 80)
        sym = await self._get_symbol()

        if porcentaje >= 100:
            return f"{categoria.title()}: {sym}{total:.2f} / {sym}{limite:.2f} ({porcentaje:.0f}%) - EXCEDIDO!"
        elif porcentaje >= alerta_pct:
            return f"{categoria.title()}: {sym}{total:.2f} / {sym}{limite:.2f} ({porcentaje:.0f}%)"
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
