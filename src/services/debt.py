from src.repository.deuda_repo import DeudaRepo


class DebtService:
    def __init__(self, deuda_repo: DeudaRepo):
        self.deuda_repo = deuda_repo

    async def plan_avalancha(self) -> str:
        """Pay highest interest rate first."""
        deudas = await self.deuda_repo.get_all()
        if not deudas:
            return "No tienes deudas activas."

        sorted_deudas = sorted(deudas, key=lambda d: d.get("tasa_interes_mensual", 0), reverse=True)
        lines = ["Plan Avalancha (mayor interes primero):"]
        for i, d in enumerate(sorted_deudas, 1):
            tasa = d.get("tasa_interes_mensual", 0)
            lines.append(f"  {i}. {d['nombre']} - S/{d['saldo_actual']:.2f} ({tasa}% mensual)")
        return "\n".join(lines)

    async def plan_bola_nieve(self) -> str:
        """Pay smallest balance first."""
        deudas = await self.deuda_repo.get_all()
        if not deudas:
            return "No tienes deudas activas."

        sorted_deudas = sorted(deudas, key=lambda d: d.get("saldo_actual", 0))
        lines = ["Plan Bola de Nieve (menor saldo primero):"]
        for i, d in enumerate(sorted_deudas, 1):
            lines.append(f"  {i}. {d['nombre']} - S/{d['saldo_actual']:.2f}")
        return "\n".join(lines)
