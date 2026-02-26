from src.database.db import get_db


class CuentaRepo:
    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM cuentas WHERE activa = 1 ORDER BY nombre")
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_id(self, cuenta_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM cuentas WHERE id = ?", (cuenta_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save(self, data: dict) -> int:
        db = await get_db()
        cuenta_id = data.get("id")
        if cuenta_id:
            await db.execute(
                """UPDATE cuentas SET nombre=?, tipo=?, moneda=?, saldo=?, color=?, activa=?
                   WHERE id=?""",
                (
                    data["nombre"], data.get("tipo", "efectivo"),
                    data.get("moneda", "PEN"), data.get("saldo", 0),
                    data.get("color", "#00f0ff"),
                    1 if data.get("activa", True) else 0,
                    cuenta_id,
                ),
            )
        else:
            cursor = await db.execute(
                """INSERT INTO cuentas (nombre, tipo, moneda, saldo, color, activa)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    data["nombre"], data.get("tipo", "efectivo"),
                    data.get("moneda", "PEN"), data.get("saldo", 0),
                    data.get("color", "#00f0ff"), 1,
                ),
            )
            cuenta_id = cursor.lastrowid
        await db.commit()
        return cuenta_id

    async def delete(self, cuenta_id: int):
        db = await get_db()
        await db.execute("UPDATE cuentas SET activa = 0 WHERE id = ?", (cuenta_id,))
        await db.commit()

    async def update_saldo(self, cuenta_id: int, delta: float):
        db = await get_db()
        await db.execute(
            "UPDATE cuentas SET saldo = saldo + ? WHERE id = ?",
            (delta, cuenta_id),
        )
        await db.commit()
