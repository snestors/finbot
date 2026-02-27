"""Repository for tarjeta billing periods (tarjeta_periodos)."""
import logging
from src.database.db import get_db

logger = logging.getLogger(__name__)


class TarjetaPeriodoRepo:
    async def get_or_create(self, tarjeta_id: int, periodo: str,
                            fecha_inicio: str, fecha_fin: str,
                            fecha_pago: str) -> dict:
        """Get existing period or create it lazily on first charge."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM tarjeta_periodos WHERE tarjeta_id = ? AND periodo = ?",
            (tarjeta_id, periodo),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        cursor = await db.execute(
            """INSERT INTO tarjeta_periodos
               (tarjeta_id, periodo, fecha_inicio, fecha_fin, fecha_pago)
               VALUES (?, ?, ?, ?, ?)""",
            (tarjeta_id, periodo, fecha_inicio, fecha_fin, fecha_pago),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "tarjeta_id": tarjeta_id,
            "periodo": periodo,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "fecha_pago": fecha_pago,
            "estado": "abierto",
            "total_facturado": 0,
            "total_pagado": 0,
        }

    async def get_by_id(self, periodo_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM tarjeta_periodos WHERE id = ?", (periodo_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_by_tarjeta(self, tarjeta_id: int) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM tarjeta_periodos WHERE tarjeta_id = ? ORDER BY periodo DESC",
            (tarjeta_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def facturar(self, periodo_id: int, total: float):
        """Mark a period as billed (facturado)."""
        db = await get_db()
        await db.execute(
            "UPDATE tarjeta_periodos SET estado = 'facturado', total_facturado = ? WHERE id = ?",
            (total, periodo_id),
        )
        await db.commit()

    async def registrar_pago(self, periodo_id: int, monto: float):
        """Register a payment against a billed period."""
        db = await get_db()
        await db.execute(
            "UPDATE tarjeta_periodos SET total_pagado = total_pagado + ? WHERE id = ?",
            (monto, periodo_id),
        )
        # Check if fully paid
        cursor = await db.execute(
            "SELECT total_facturado, total_pagado FROM tarjeta_periodos WHERE id = ?",
            (periodo_id,),
        )
        row = await cursor.fetchone()
        if row and row["total_pagado"] >= row["total_facturado"]:
            await db.execute(
                "UPDATE tarjeta_periodos SET estado = 'pagado' WHERE id = ?",
                (periodo_id,),
            )
        await db.commit()

    async def get_oldest_facturado(self, tarjeta_id: int) -> dict | None:
        """Get the oldest unpaid billed period for payment application."""
        db = await get_db()
        cursor = await db.execute(
            """SELECT * FROM tarjeta_periodos
               WHERE tarjeta_id = ? AND estado = 'facturado'
               ORDER BY periodo ASC LIMIT 1""",
            (tarjeta_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_abiertos_para_facturar(self, dia_corte: int) -> list[dict]:
        """Get open periods that should be billed based on corte day."""
        db = await get_db()
        cursor = await db.execute(
            """SELECT tp.*, t.fecha_corte FROM tarjeta_periodos tp
               JOIN tarjetas t ON t.id = tp.tarjeta_id
               WHERE tp.estado = 'abierto' AND t.fecha_corte = ?""",
            (dia_corte,),
        )
        return [dict(r) for r in await cursor.fetchall()]
