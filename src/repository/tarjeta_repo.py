"""Repository for tarjetas (credit/debit cards)."""
import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _today() -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def _clamp_day(year: int, month: int, day: int) -> date:
    """Create a date clamping the day to the month's max."""
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, max_day))


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping the day."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return _clamp_day(year, month, d.day)


class TarjetaRepo:
    async def get_all(self, solo_activas: bool = True) -> list[dict]:
        db = await get_db()
        if solo_activas:
            rows = await db.execute_fetchall("SELECT * FROM tarjetas WHERE activa = 1")
        else:
            rows = await db.execute_fetchall("SELECT * FROM tarjetas")
        result = []
        for r in rows:
            t = dict(r)
            t["saldo_usado"] = await self.calcular_saldo_usado(t["id"])
            result.append(t)
        return result

    async def save(self, data: dict) -> int:
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO tarjetas (nombre, banco, tipo, ultimos_4, limite_credito, fecha_corte, fecha_pago, moneda)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["nombre"], data.get("banco", ""), data.get("tipo", "credito"),
             data.get("ultimos_4", ""), data.get("limite_credito", 0),
             data.get("fecha_corte", 1), data.get("fecha_pago", 15),
             data.get("moneda", "PEN"))
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_id(self, tarjeta_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM tarjetas WHERE id = ?", (tarjeta_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        t = dict(row)
        t["saldo_usado"] = await self.calcular_saldo_usado(t["id"])
        return t

    async def calcular_saldo_usado(self, tarjeta_id: int) -> float:
        """Calculate used balance: SUM(charges) - SUM(payments) from unified movimientos."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM movimientos WHERE tarjeta_id = ? AND tipo = 'gasto'",
            (tarjeta_id,),
        )
        cargos = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM movimientos WHERE tarjeta_id = ? AND tipo = 'pago_tarjeta'",
            (tarjeta_id,),
        )
        pagos = (await cursor.fetchone())[0]
        return round(max(0, cargos - pagos), 2)

    async def delete(self, tarjeta_id: int):
        db = await get_db()
        await db.execute("UPDATE tarjetas SET activa = 0 WHERE id = ?", (tarjeta_id,))
        await db.commit()

    def get_billing_period(self, tarjeta: dict, target_date: date = None) -> dict:
        """Calculate the billing period for a card on a given date.

        If fecha_corte=15:
          - Period closing on the 15th: runs from prev_month 16th to this_month 15th
          - Payment due: fecha_pago day of the month after period end

        Returns: {inicio: str, fin: str, fecha_pago: str, periodo: "YYYY-MM"}
        """
        today = target_date or _today()
        corte_dia = tarjeta.get("fecha_corte", 1) or 1
        pago_dia = tarjeta.get("fecha_pago", 15) or 15

        if today.day > corte_dia:
            # Past corte day: current period is (corte+1 this month) to (corte next month)
            corte_this = _clamp_day(today.year, today.month, corte_dia)
            inicio = corte_this + timedelta(days=1)
            fin = _add_months(corte_this, 1)
        else:
            # On or before corte day: period is (corte+1 prev month) to (corte this month)
            fin = _clamp_day(today.year, today.month, corte_dia)
            corte_prev = _add_months(fin, -1)
            inicio = corte_prev + timedelta(days=1)

        # Payment due: pago_dia of the month after period end
        pago_month = _add_months(fin, 1)
        fecha_pago = _clamp_day(pago_month.year, pago_month.month, pago_dia)

        return {
            "inicio": inicio.isoformat(),
            "fin": fin.isoformat(),
            "fecha_pago": fecha_pago.isoformat(),
            "periodo": fin.strftime("%Y-%m"),
        }

    def get_next_cuota_date(self, tarjeta: dict, from_date: date = None) -> date:
        """Get the next billing period's corte date for installment charges."""
        period = self.get_billing_period(tarjeta, from_date)
        fin = date.fromisoformat(period["fin"])
        return _add_months(fin, 1)
