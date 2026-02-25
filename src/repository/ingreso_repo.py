from datetime import datetime
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


class IngresoRepo:
    async def create(self, monto: float, fuente: str, descripcion: str = "") -> int:
        now = _now()
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO ingresos (monto, fuente, descripcion, mes, fecha)
               VALUES (?, ?, ?, ?, ?)""",
            (monto, fuente, descripcion or fuente, now.strftime("%Y-%m"), now.isoformat()),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_month(self, mes: str | None = None) -> list[dict]:
        mes = mes or _now().strftime("%Y-%m")
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM ingresos WHERE mes = ? ORDER BY fecha DESC", (mes,)
        )
        return [dict(r) for r in await cursor.fetchall()]
