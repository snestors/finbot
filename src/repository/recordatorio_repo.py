from src.database.db import get_db


class RecordatorioRepo:
    async def save(self, mensaje: str, hora: str, dias: str = "todos") -> int:
        db = await get_db()
        cursor = await db.execute(
            "INSERT INTO recordatorios (mensaje, hora, dias) VALUES (?, ?, ?)",
            (mensaje, hora, dias),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_activos(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM recordatorios WHERE activo = 1 ORDER BY hora"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def delete(self, recordatorio_id: int):
        db = await get_db()
        await db.execute("DELETE FROM recordatorios WHERE id = ?", (recordatorio_id,))
        await db.commit()

    async def desactivar(self, recordatorio_id: int):
        db = await get_db()
        await db.execute(
            "UPDATE recordatorios SET activo = 0 WHERE id = ?", (recordatorio_id,)
        )
        await db.commit()
