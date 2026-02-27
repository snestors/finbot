"""Repository for credit card payments (pago_tarjeta)."""
from datetime import datetime
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


class PagoTarjetaRepo:
    async def create(self, tarjeta_id: int, cuenta_id: int, monto: float,
                     moneda: str = "PEN", monto_cuenta: float = None,
                     descripcion: str = "") -> int:
        db = await get_db()
        mc = monto_cuenta if monto_cuenta is not None else monto
        cursor = await db.execute(
            """INSERT INTO pago_tarjeta
               (tarjeta_id, cuenta_id, monto, moneda, monto_cuenta, fecha, descripcion)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tarjeta_id, cuenta_id, monto, moneda, mc, _now().isoformat(), descripcion),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_tarjeta(self, tarjeta_id: int, limit: int = 30) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """SELECT pt.*, c.nombre as cuenta_nombre
               FROM pago_tarjeta pt
               LEFT JOIN cuentas c ON c.id = pt.cuenta_id
               WHERE pt.tarjeta_id = ?
               ORDER BY pt.fecha DESC LIMIT ?""",
            (tarjeta_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_cuenta(self, cuenta_id: int, limit: int = 30) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """SELECT pt.*, t.nombre as tarjeta_nombre
               FROM pago_tarjeta pt
               LEFT JOIN tarjetas t ON t.id = pt.tarjeta_id
               WHERE pt.cuenta_id = ?
               ORDER BY pt.fecha DESC LIMIT ?""",
            (cuenta_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]
