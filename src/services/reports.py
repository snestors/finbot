from src.repository.gasto_repo import GastoRepo


class ReportService:
    def __init__(self, gasto_repo: GastoRepo):
        self.gasto_repo = gasto_repo

    async def resumen_completo(self, mes: str | None = None) -> str:
        gastos = await self.gasto_repo.get_by_month(mes)
        if not gastos:
            return "No hay gastos en este periodo."

        total = sum(g["monto"] for g in gastos)
        by_cat: dict[str, float] = {}
        for g in gastos:
            cat = g["categoria"]
            by_cat[cat] = by_cat.get(cat, 0) + g["monto"]

        lines = [f"Resumen del mes ({len(gastos)} transacciones):"]
        for cat, monto in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = monto / total * 100
            lines.append(f"  {cat.title()}: S/{monto:.2f} ({pct:.0f}%)")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)
