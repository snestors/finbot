"""Repository for gasto installments (cuotas)."""
from datetime import date
from dateutil.relativedelta import relativedelta
from src.database.db import get_db


class GastoCuotaRepo:
    async def create_cuotas(self, gasto_id: int, cuotas_total: int,
                            monto_total: float, tarjeta_id: int,
                            fecha_primera_cuota: date) -> list[int]:
        """Generate all installment records for a gasto bought in cuotas."""
        db = await get_db()
        monto_cuota = round(monto_total / cuotas_total, 2)
        ids = []
        for i in range(cuotas_total):
            fecha_cargo = fecha_primera_cuota + relativedelta(months=i)
            periodo = fecha_cargo.strftime("%Y-%m")
            cursor = await db.execute(
                """INSERT INTO gasto_cuotas
                   (gasto_id, numero_cuota, cuotas_total, monto_cuota,
                    fecha_cargo, tarjeta_id, periodo_facturacion)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (gasto_id, i + 1, cuotas_total, monto_cuota,
                 fecha_cargo.isoformat(), tarjeta_id, periodo),
            )
            ids.append(cursor.lastrowid)
        await db.commit()
        return ids

    async def get_by_gasto(self, gasto_id: int) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM gasto_cuotas WHERE gasto_id = ? ORDER BY numero_cuota",
            (gasto_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_pendientes_tarjeta(self, tarjeta_id: int,
                                     periodo: str = None) -> list[dict]:
        """Get unpaid installments for a card, optionally filtered by billing period."""
        db = await get_db()
        if periodo:
            cursor = await db.execute(
                """SELECT gc.*, g.descripcion, g.categoria, g.comercio, g.monto as monto_total_gasto
                   FROM gasto_cuotas gc
                   JOIN gastos g ON gc.gasto_id = g.id
                   WHERE gc.tarjeta_id = ? AND gc.periodo_facturacion = ? AND gc.pagada = 0
                   ORDER BY gc.fecha_cargo""",
                (tarjeta_id, periodo),
            )
        else:
            cursor = await db.execute(
                """SELECT gc.*, g.descripcion, g.categoria, g.comercio, g.monto as monto_total_gasto
                   FROM gasto_cuotas gc
                   JOIN gastos g ON gc.gasto_id = g.id
                   WHERE gc.tarjeta_id = ? AND gc.pagada = 0
                   ORDER BY gc.fecha_cargo""",
                (tarjeta_id,),
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def marcar_pagada(self, cuota_id: int):
        db = await get_db()
        await db.execute(
            "UPDATE gasto_cuotas SET pagada = 1 WHERE id = ?", (cuota_id,)
        )
        await db.commit()

    async def delete_by_gasto(self, gasto_id: int):
        db = await get_db()
        await db.execute(
            "DELETE FROM gasto_cuotas WHERE gasto_id = ?", (gasto_id,)
        )
        await db.commit()
