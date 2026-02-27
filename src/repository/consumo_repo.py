import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.database.db import get_db

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Lima")


def _now():
    return datetime.now(TZ)


def _mes_actual():
    return _now().strftime("%Y-%m")


class ConsumoRepo:

    async def create(self, tipo: str, valor: float, unidad: str,
                     fecha: str, source: str = "manual",
                     costo: float | None = None) -> int:
        db = await get_db()
        mes = fecha[:7]  # "YYYY-MM"
        cursor = await db.execute(
            """INSERT INTO consumos (tipo, valor, unidad, costo, fecha, mes, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tipo, valor, unidad, costo, fecha, mes, source),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_month(self, tipo: str, mes: str = None) -> list[dict]:
        db = await get_db()
        mes = mes or _mes_actual()
        cursor = await db.execute(
            "SELECT * FROM consumos WHERE tipo = ? AND mes = ? ORDER BY fecha DESC",
            (tipo, mes),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_resumen(self, tipo: str, mes: str = None) -> dict:
        db = await get_db()
        mes = mes or _mes_actual()
        cursor = await db.execute(
            """SELECT COUNT(*) as lecturas,
                      COALESCE(SUM(valor), 0) as total,
                      COALESCE(AVG(valor), 0) as promedio,
                      COALESCE(SUM(costo), 0) as costo_total,
                      MIN(fecha) as desde,
                      MAX(fecha) as hasta
               FROM consumos WHERE tipo = ? AND mes = ?""",
            (tipo, mes),
        )
        row = dict(await cursor.fetchone())
        row["tipo"] = tipo
        row["mes"] = mes
        return row

    async def get_all_resumen(self, mes: str = None) -> list[dict]:
        result = []
        for tipo in ("luz", "agua", "gas"):
            r = await self.get_resumen(tipo, mes)
            if r["lecturas"] > 0:
                result.append(r)
        return result

    async def get_latest(self, tipo: str) -> dict | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM consumos WHERE tipo = ? ORDER BY fecha DESC, id DESC LIMIT 1",
            (tipo,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_5min_sonoff(self, power_w: float, voltage_v: float,
                                current_a: float, day_kwh: float,
                                month_kwh: float):
        """Save a Sonoff reading with all power fields. Dedup by rounded minute."""
        now = _now()
        fecha = now.strftime("%Y-%m-%dT%H:%M:00")
        mes = now.strftime("%Y-%m")

        db = await get_db()
        cursor = await db.execute(
            "SELECT id FROM consumos WHERE tipo = 'luz' AND source = 'sonoff' AND fecha = ?",
            (fecha,),
        )
        if await cursor.fetchone():
            return  # Already have this slot

        await db.execute(
            """INSERT INTO consumos (tipo, valor, unidad, fecha, mes, source,
                                     power_w, voltage_v, current_a, day_kwh, month_kwh)
               VALUES ('luz', ?, 'kWh', ?, ?, 'sonoff', ?, ?, ?, ?, ?)""",
            (day_kwh, fecha, mes, power_w, voltage_v, current_a, day_kwh, month_kwh),
        )
        await db.commit()
        logger.debug(f"Sonoff 5min saved: {power_w}W {day_kwh}kWh at {fecha}")

    async def save_hourly_sonoff(self, power_w: float, voltage: float,
                                  current: float, day_kwh: float,
                                  month_kwh: float):
        """Legacy hourly save — redirects to 5min save."""
        await self.save_5min_sonoff(power_w, voltage, current, day_kwh, month_kwh)

    async def get_chart_data(self, tipo: str, desde: str, hasta: str,
                              slice_hours: int = 1) -> list[dict]:
        """Get aggregated data for charting. Groups by slice_hours intervals."""
        db = await get_db()

        if slice_hours <= 1:
            # Raw 5-min data
            cursor = await db.execute(
                """SELECT fecha, power_w, voltage_v, current_a, day_kwh, month_kwh
                   FROM consumos
                   WHERE tipo = ? AND source = 'sonoff'
                   AND fecha >= ? AND fecha <= ?
                   ORDER BY fecha""",
                (tipo, desde, hasta),
            )
            return [dict(r) for r in await cursor.fetchall()]

        if slice_hours >= 24:
            # Group by day
            cursor = await db.execute(
                """SELECT substr(fecha, 1, 10) as fecha,
                          AVG(power_w) as power_w,
                          AVG(voltage_v) as voltage_v,
                          AVG(current_a) as current_a,
                          MAX(day_kwh) as day_kwh,
                          MAX(month_kwh) as month_kwh
                   FROM consumos
                   WHERE tipo = ? AND source = 'sonoff'
                   AND fecha >= ? AND fecha <= ?
                   GROUP BY substr(fecha, 1, 10)
                   ORDER BY fecha""",
                (tipo, desde, hasta),
            )
        elif slice_hours >= 8:
            # Group by 8h blocks (0-7, 8-15, 16-23)
            cursor = await db.execute(
                """SELECT substr(fecha, 1, 10) || 'T' ||
                          printf('%02d', (CAST(substr(fecha, 12, 2) AS INTEGER) / 8) * 8)
                          || ':00:00' as fecha,
                          AVG(power_w) as power_w,
                          AVG(voltage_v) as voltage_v,
                          AVG(current_a) as current_a,
                          MAX(day_kwh) as day_kwh,
                          MAX(month_kwh) as month_kwh
                   FROM consumos
                   WHERE tipo = ? AND source = 'sonoff'
                   AND fecha >= ? AND fecha <= ?
                   GROUP BY substr(fecha, 1, 10) || 'T' ||
                            printf('%02d', (CAST(substr(fecha, 12, 2) AS INTEGER) / 8) * 8)
                   ORDER BY fecha""",
                (tipo, desde, hasta),
            )
        else:
            # Group by hour
            cursor = await db.execute(
                """SELECT substr(fecha, 1, 13) || ':00:00' as fecha,
                          AVG(power_w) as power_w,
                          AVG(voltage_v) as voltage_v,
                          AVG(current_a) as current_a,
                          MAX(day_kwh) as day_kwh,
                          MAX(month_kwh) as month_kwh
                   FROM consumos
                   WHERE tipo = ? AND source = 'sonoff'
                   AND fecha >= ? AND fecha <= ?
                   GROUP BY substr(fecha, 1, 13)
                   ORDER BY fecha""",
                (tipo, desde, hasta),
            )

        return [dict(r) for r in await cursor.fetchall()]

    async def get_consumo_periodo(self, tipo: str, desde: str, hasta: str) -> dict:
        """Calculate total kWh for a period by summing MAX(day_kwh) per day."""
        db = await get_db()
        cursor = await db.execute(
            """SELECT COALESCE(SUM(max_day), 0) as kwh_total,
                      COUNT(*) as dias
               FROM (
                   SELECT MAX(day_kwh) as max_day
                   FROM consumos
                   WHERE tipo = ? AND source = 'sonoff'
                   AND fecha >= ? AND fecha <= ?
                   GROUP BY substr(fecha, 1, 10)
               )""",
            (tipo, desde, hasta),
        )
        row = dict(await cursor.fetchone())
        row["tipo"] = tipo
        row["desde"] = desde
        row["hasta"] = hasta
        return row

    async def get_hoy_resumen(self) -> dict | None:
        """Get today's energy summary for context building."""
        db = await get_db()
        hoy = _now().strftime("%Y-%m-%d")
        cursor = await db.execute(
            """SELECT AVG(power_w) as avg_power, MAX(power_w) as max_power,
                      AVG(current_a) as avg_current,
                      MAX(day_kwh) as day_kwh, MAX(month_kwh) as month_kwh,
                      COUNT(*) as lecturas
               FROM consumos
               WHERE tipo = 'luz' AND source = 'sonoff'
               AND fecha >= ?""",
            (hoy,),
        )
        row = dict(await cursor.fetchone())
        if not row["lecturas"]:
            return None
        return row

    async def get_mes_resumen_energia(self, mes: str = None) -> dict | None:
        """Get monthly energy summary."""
        db = await get_db()
        mes = mes or _mes_actual()
        cursor = await db.execute(
            """SELECT COALESCE(SUM(max_day), 0) as kwh_total,
                      COUNT(*) as dias
               FROM (
                   SELECT MAX(day_kwh) as max_day
                   FROM consumos
                   WHERE tipo = 'luz' AND source = 'sonoff'
                   AND mes = ?
                   GROUP BY substr(fecha, 1, 10)
               )""",
            (mes,),
        )
        row = dict(await cursor.fetchone())
        row["mes"] = mes
        return row

    async def delete(self, consumo_id: int):
        db = await get_db()
        await db.execute("DELETE FROM consumos WHERE id = ?", (consumo_id,))
        await db.commit()
