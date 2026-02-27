"""Repository for transferencias between accounts."""
from datetime import datetime
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


class TransferenciaRepo:
    async def create(self, cuenta_origen_id: int, cuenta_destino_id: int,
                     monto: float, moneda: str = "PEN",
                     monto_origen: float = None, monto_destino: float = None,
                     descripcion: str = "") -> int:
        db = await get_db()
        mo = monto_origen if monto_origen is not None else monto
        md = monto_destino if monto_destino is not None else monto
        cursor = await db.execute(
            """INSERT INTO transferencias
               (cuenta_origen_id, cuenta_destino_id, monto, moneda,
                monto_origen, monto_destino, descripcion, fecha)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (cuenta_origen_id, cuenta_destino_id, monto, moneda,
             mo, md, descripcion, _now().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_cuenta(self, cuenta_id: int, limit: int = 30) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """SELECT t.*, co.nombre as cuenta_origen, cd.nombre as cuenta_destino
               FROM transferencias t
               LEFT JOIN cuentas co ON co.id = t.cuenta_origen_id
               LEFT JOIN cuentas cd ON cd.id = t.cuenta_destino_id
               WHERE t.cuenta_origen_id = ? OR t.cuenta_destino_id = ?
               ORDER BY t.fecha DESC LIMIT ?""",
            (cuenta_id, cuenta_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_all(self, limit: int = 50) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """SELECT t.*, co.nombre as cuenta_origen, cd.nombre as cuenta_destino
               FROM transferencias t
               LEFT JOIN cuentas co ON co.id = t.cuenta_origen_id
               LEFT JOIN cuentas cd ON cd.id = t.cuenta_destino_id
               ORDER BY t.fecha DESC LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in await cursor.fetchall()]
