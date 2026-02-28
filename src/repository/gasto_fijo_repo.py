"""Repository for gastos fijos (recurring expenses)."""
from datetime import date, timedelta

from src.database.db import get_db


def is_due_today(gf: dict, today: date) -> bool:
    """Check if a gasto fijo is due on the given date based on its frequency."""
    freq = gf.get("frecuencia", "mensual")
    dia = gf.get("dia", 1)

    if freq == "mensual":
        # For months shorter than dia, trigger on last day
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        target = min(dia, last_day)
        return today.day == target

    if freq == "semanal":
        # dia = 0 (lun) to 6 (dom)
        return today.weekday() == dia

    if freq == "quincenal":
        # Triggers on dia and dia+15 (capped at month end)
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        d1 = min(dia, last_day)
        d2 = min(dia + 15, last_day) if dia + 15 <= 28 else min(dia - 15 + 30, last_day)
        return today.day in (d1, d2)

    if freq == "anual":
        mes = gf.get("mes", 1)
        if today.month != mes:
            return False
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        return today.day == min(dia, last_day)

    return False


def is_already_registered(gf: dict, today: date) -> bool:
    """Check if the gasto fijo was already registered for the current period."""
    ultimo = gf.get("ultimo_registro")
    if not ultimo:
        return False

    try:
        last = date.fromisoformat(ultimo[:10])
    except (ValueError, TypeError):
        return False

    freq = gf.get("frecuencia", "mensual")

    if freq == "mensual":
        return last.year == today.year and last.month == today.month

    if freq == "semanal":
        # Same ISO week
        return last.isocalendar()[:2] == today.isocalendar()[:2]

    if freq == "quincenal":
        # Same half-month: 1-15 or 16-end
        return (last.year == today.year and last.month == today.month
                and (last.day <= 15) == (today.day <= 15))

    if freq == "anual":
        return last.year == today.year

    return False


class GastoFijoRepo:
    async def create(self, nombre: str, monto: float, frecuencia: str = "mensual",
                     dia: int = 1, **kwargs) -> int:
        db = await get_db()
        cols = ["nombre", "monto", "frecuencia", "dia"]
        vals = [nombre, monto, frecuencia, dia]
        for key in ("moneda", "categoria", "descripcion", "comercio",
                     "metodo_pago", "cuenta_id", "tarjeta_id", "mes"):
            if key in kwargs and kwargs[key] is not None:
                cols.append(key)
                vals.append(kwargs[key])
        placeholders = ",".join("?" * len(cols))
        col_names = ",".join(cols)
        cursor = await db.execute(
            f"INSERT INTO gastos_fijos ({col_names}) VALUES ({placeholders})", vals
        )
        await db.commit()
        return cursor.lastrowid

    async def get_all(self, solo_activos: bool = True) -> list[dict]:
        db = await get_db()
        q = "SELECT * FROM gastos_fijos"
        if solo_activos:
            q += " WHERE activo = 1"
        q += " ORDER BY nombre"
        cursor = await db.execute(q)
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_id(self, gf_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM gastos_fijos WHERE id = ?", (gf_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update(self, gf_id: int, **fields) -> bool:
        if not fields:
            return False
        db = await get_db()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [gf_id]
        await db.execute(f"UPDATE gastos_fijos SET {sets} WHERE id = ?", vals)
        await db.commit()
        return True

    async def delete(self, gf_id: int):
        db = await get_db()
        await db.execute("DELETE FROM gastos_fijos WHERE id = ?", (gf_id,))
        await db.commit()

    async def desactivar(self, gf_id: int):
        db = await get_db()
        await db.execute("UPDATE gastos_fijos SET activo = 0 WHERE id = ?", (gf_id,))
        await db.commit()

    async def activar(self, gf_id: int):
        db = await get_db()
        await db.execute("UPDATE gastos_fijos SET activo = 1 WHERE id = ?", (gf_id,))
        await db.commit()

    async def registrar(self, gf_id: int, movimiento_id: int, fecha: str):
        db = await get_db()
        await db.execute(
            "UPDATE gastos_fijos SET ultimo_registro = ?, ultimo_movimiento_id = ? WHERE id = ?",
            (fecha, movimiento_id, gf_id),
        )
        await db.commit()
