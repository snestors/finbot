"""Repository for historical exchange rates (SUNAT USD/PEN)."""
from src.database.db import get_db


class TipoCambioRepo:
    async def save(self, fecha: str, compra: float, venta: float,
                   fuente: str = "SUNAT"):
        """Insert or update exchange rate for a given date."""
        db = await get_db()
        await db.execute(
            """INSERT INTO tipo_cambio_historico (fecha, compra, venta, fuente)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(fecha) DO UPDATE SET
                   compra = excluded.compra,
                   venta = excluded.venta,
                   fuente = excluded.fuente""",
            (fecha, compra, venta, fuente),
        )
        await db.commit()

    async def get_by_fecha(self, fecha: str) -> dict | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM tipo_cambio_historico WHERE fecha = ?", (fecha,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_historico(self, dias: int = 30) -> list[dict]:
        """Get last N days of exchange rates, ordered by date DESC."""
        db = await get_db()
        cursor = await db.execute(
            """SELECT * FROM tipo_cambio_historico
               ORDER BY fecha DESC LIMIT ?""",
            (dias,),
        )
        return [dict(r) for r in await cursor.fetchall()]
