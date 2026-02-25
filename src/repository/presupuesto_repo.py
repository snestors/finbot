from src.database.db import get_db


class PresupuestoRepo:
    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM presupuestos ORDER BY categoria")
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_categoria(self, categoria: str) -> dict | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM presupuestos WHERE categoria = ?", (categoria,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save(self, data: dict) -> int:
        db = await get_db()
        existing = await self.get_by_categoria(data["categoria"])
        if existing:
            await db.execute(
                "UPDATE presupuestos SET limite_mensual = ?, alerta_porcentaje = ? WHERE id = ?",
                (data["limite_mensual"], data.get("alerta_porcentaje", 80), existing["id"]),
            )
            await db.commit()
            return existing["id"]
        else:
            cursor = await db.execute(
                "INSERT INTO presupuestos (categoria, limite_mensual, alerta_porcentaje) VALUES (?, ?, ?)",
                (data["categoria"], data["limite_mensual"], data.get("alerta_porcentaje", 80)),
            )
            await db.commit()
            return cursor.lastrowid
