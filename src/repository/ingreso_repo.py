from datetime import datetime
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


class IngresoRepo:
    async def create(self, monto: float, fuente: str, descripcion: str = "",
                     moneda: str = "PEN", cuenta_id: int = None,
                     monto_cuenta: float = None) -> int:
        now = _now()
        mc = monto_cuenta if monto_cuenta is not None else monto
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO ingresos (monto, fuente, descripcion, mes, fecha, moneda, cuenta_id, monto_cuenta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (monto, fuente, descripcion or fuente, now.strftime("%Y-%m"), now.isoformat(),
             moneda, cuenta_id, mc),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_id(self, ingreso_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM ingresos WHERE id = ?", (ingreso_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update(self, ingreso_id: int, **fields) -> bool:
        if not fields:
            return False
        db = await get_db()
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [ingreso_id]
        await db.execute(f"UPDATE ingresos SET {sets} WHERE id = ?", values)
        await db.commit()
        return True

    async def delete(self, ingreso_id: int):
        db = await get_db()
        await db.execute("DELETE FROM ingresos WHERE id = ?", (ingreso_id,))
        await db.commit()

    async def get_by_month(self, mes: str | None = None) -> list[dict]:
        mes = mes or _now().strftime("%Y-%m")
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM ingresos WHERE mes = ? ORDER BY fecha DESC", (mes,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def buscar(self, texto: str, limit: int = 20) -> list[dict]:
        db = await get_db()
        patron = f"%{texto}%"
        cursor = await db.execute(
            """SELECT * FROM ingresos
               WHERE descripcion LIKE ? OR fuente LIKE ?
               ORDER BY fecha DESC LIMIT ?""",
            (patron, patron, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]
