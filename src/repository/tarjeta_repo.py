"""Repository for tarjetas (credit/debit cards)."""
from src.database.db import get_db


class TarjetaRepo:
    async def get_all(self, solo_activas: bool = True) -> list[dict]:
        db = await get_db()
        if solo_activas:
            rows = await db.execute_fetchall("SELECT * FROM tarjetas WHERE activa = 1")
        else:
            rows = await db.execute_fetchall("SELECT * FROM tarjetas")
        return [dict(r) for r in rows]

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

    async def delete(self, tarjeta_id: int):
        db = await get_db()
        await db.execute("UPDATE tarjetas SET activa = 0 WHERE id = ?", (tarjeta_id,))
        await db.commit()
