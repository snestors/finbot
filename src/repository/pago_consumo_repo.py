import logging

from src.database.db import get_db

logger = logging.getLogger(__name__)


class PagoConsumoRepo:

    async def create(self, tipo: str, monto: float, fecha_pago: str,
                     fecha_desde: str, fecha_hasta: str,
                     kwh_periodo: float | None = None,
                     costo_kwh: float | None = None,
                     notas: str = "") -> int:
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO pagos_consumo
               (tipo, monto, fecha_pago, fecha_desde, fecha_hasta, kwh_periodo, costo_kwh, notas)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tipo, monto, fecha_pago, fecha_desde, fecha_hasta, kwh_periodo, costo_kwh, notas),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_all(self, tipo: str = "luz") -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM pagos_consumo WHERE tipo = ? ORDER BY fecha_pago DESC",
            (tipo,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_id(self, pago_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM pagos_consumo WHERE id = ?", (pago_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete(self, pago_id: int):
        db = await get_db()
        await db.execute("DELETE FROM pagos_consumo WHERE id = ?", (pago_id,))
        await db.commit()

    async def get_resumen(self, tipo: str = "luz") -> dict:
        db = await get_db()
        cursor = await db.execute(
            """SELECT COUNT(*) as total_pagos,
                      COALESCE(SUM(monto), 0) as total_monto,
                      COALESCE(AVG(monto), 0) as promedio_monto,
                      COALESCE(AVG(costo_kwh), 0) as promedio_costo_kwh,
                      MAX(fecha_pago) as ultimo_pago
               FROM pagos_consumo WHERE tipo = ?""",
            (tipo,),
        )
        row = dict(await cursor.fetchone())
        row["tipo"] = tipo
        return row

    async def get_ultimo(self, tipo: str = "luz") -> dict | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM pagos_consumo WHERE tipo = ? ORDER BY fecha_pago DESC LIMIT 1",
            (tipo,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
