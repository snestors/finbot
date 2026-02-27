"""Repository for movimiento installments (movimiento_cuotas)."""
from datetime import date
from dateutil.relativedelta import relativedelta
from src.database.db import get_db


class MovimientoCuotaRepo:
    async def create_cuotas(self, movimiento_id: int, cuotas_total: int,
                            monto_total: float, tarjeta_id: int,
                            fecha_primera_cuota: date,
                            tarjeta_periodo_id: int = None) -> list[int]:
        """Generate all installment records for a movimiento bought in cuotas."""
        db = await get_db()
        monto_cuota = round(monto_total / cuotas_total, 2)
        ids = []
        for i in range(cuotas_total):
            fecha_cargo = fecha_primera_cuota + relativedelta(months=i)
            periodo = fecha_cargo.strftime("%Y-%m")
            cursor = await db.execute(
                """INSERT INTO movimiento_cuotas
                   (movimiento_id, tarjeta_id, tarjeta_periodo_id, numero_cuota,
                    cuotas_total, monto_cuota, fecha_cargo, periodo_facturacion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (movimiento_id, tarjeta_id, tarjeta_periodo_id,
                 i + 1, cuotas_total, monto_cuota,
                 fecha_cargo.isoformat(), periodo),
            )
            ids.append(cursor.lastrowid)
        await db.commit()
        return ids

    async def get_by_movimiento(self, movimiento_id: int) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM movimiento_cuotas WHERE movimiento_id = ? ORDER BY numero_cuota",
            (movimiento_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_pendientes_tarjeta(self, tarjeta_id: int,
                                     periodo: str = None) -> list[dict]:
        """Get unpaid installments for a card, optionally filtered by billing period."""
        db = await get_db()
        if periodo:
            cursor = await db.execute(
                """SELECT mc.*, m.descripcion, m.categoria, m.comercio, m.monto as monto_total_mov
                   FROM movimiento_cuotas mc
                   JOIN movimientos m ON mc.movimiento_id = m.id
                   WHERE mc.tarjeta_id = ? AND mc.periodo_facturacion = ? AND mc.pagada = 0
                   ORDER BY mc.fecha_cargo""",
                (tarjeta_id, periodo),
            )
        else:
            cursor = await db.execute(
                """SELECT mc.*, m.descripcion, m.categoria, m.comercio, m.monto as monto_total_mov
                   FROM movimiento_cuotas mc
                   JOIN movimientos m ON mc.movimiento_id = m.id
                   WHERE mc.tarjeta_id = ? AND mc.pagada = 0
                   ORDER BY mc.fecha_cargo""",
                (tarjeta_id,),
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def marcar_pagada(self, cuota_id: int):
        db = await get_db()
        await db.execute(
            "UPDATE movimiento_cuotas SET pagada = 1 WHERE id = ?", (cuota_id,)
        )
        await db.commit()

    async def delete_by_movimiento(self, movimiento_id: int):
        db = await get_db()
        await db.execute(
            "DELETE FROM movimiento_cuotas WHERE movimiento_id = ?", (movimiento_id,)
        )
        await db.commit()
