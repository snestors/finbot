from datetime import datetime
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


def _mes_actual() -> str:
    return _now().strftime("%Y-%m")


def _semana_actual() -> str:
    return _now().strftime("%Y-W%V")


def _inicio_hoy() -> str:
    return _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


class GastoRepo:
    async def create(self, monto: float, categoria: str, descripcion: str, fuente: str,
                     moneda: str = "PEN", comercio: str = None,
                     metodo_pago: str = None, cuenta_id: int = None,
                     tarjeta_id: int = None, cuotas: int = 0,
                     monto_cuenta: float = None) -> int:
        now = _now()
        db = await get_db()
        mc = monto_cuenta if monto_cuenta is not None else monto
        cursor = await db.execute(
            """INSERT INTO gastos (monto, categoria, descripcion, fuente, fecha, mes, semana,
                                   moneda, comercio, metodo_pago, cuenta_id, tarjeta_id, cuotas, monto_cuenta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (monto, categoria, descripcion, fuente,
             now.isoformat(), now.strftime("%Y-%m"), now.strftime("%Y-W%V"),
             moneda, comercio, metodo_pago, cuenta_id, tarjeta_id, cuotas, mc),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_id(self, gasto_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM gastos WHERE id = ?", (gasto_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update(self, gasto_id: int, **fields) -> bool:
        if not fields:
            return False
        db = await get_db()
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [gasto_id]
        await db.execute(f"UPDATE gastos SET {sets} WHERE id = ?", values)
        await db.commit()
        return True

    async def get_by_month(self, mes: str | None = None) -> list[dict]:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM gastos WHERE mes = ? ORDER BY fecha DESC", (mes,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_today(self) -> list[dict]:
        inicio = _inicio_hoy()
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM gastos WHERE fecha >= ? ORDER BY fecha DESC", (inicio,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def delete(self, gasto_id: int):
        db = await get_db()
        await db.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))
        await db.commit()

    async def resumen_hoy(self) -> str:
        gastos = await self.get_today()
        if not gastos:
            return "Hoy no has registrado gastos."
        total = sum(g["monto"] for g in gastos)
        lines = [f"Gastos de hoy ({len(gastos)}):"]
        by_cat: dict[str, float] = {}
        for g in gastos:
            cat = g["categoria"]
            by_cat[cat] = by_cat.get(cat, 0) + g["monto"]
        for cat, monto in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  | {cat.title()}: S/{monto:.2f}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)

    async def resumen_semana(self) -> str:
        semana = _semana_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM gastos WHERE semana = ?", (semana,)
        )
        gastos = [dict(r) for r in await cursor.fetchall()]
        if not gastos:
            return "Esta semana no hay gastos registrados."
        total = sum(g["monto"] for g in gastos)
        lines = [f"Gastos de la semana ({len(gastos)}):"]
        by_cat: dict[str, float] = {}
        for g in gastos:
            cat = g["categoria"]
            by_cat[cat] = by_cat.get(cat, 0) + g["monto"]
        for cat, monto in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  | {cat.title()}: S/{monto:.2f}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)

    async def resumen_mes(self) -> str:
        gastos = await self.get_by_month()
        if not gastos:
            return "Este mes no hay gastos registrados."
        total = sum(g["monto"] for g in gastos)
        lines = [f"Gastos del mes ({len(gastos)}):"]
        by_cat: dict[str, float] = {}
        for g in gastos:
            cat = g["categoria"]
            by_cat[cat] = by_cat.get(cat, 0) + g["monto"]
        for cat, monto in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  | {cat.title()}: S/{monto:.2f}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)

    async def resumen_categorias(self, mes: str | None = None) -> dict:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT categoria, SUM(monto) as total FROM gastos WHERE mes = ? GROUP BY categoria",
            (mes,),
        )
        return {row["categoria"]: row["total"] for row in await cursor.fetchall()}

    async def total_categoria_mes(self, categoria: str, mes: str | None = None) -> float:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT COALESCE(SUM(monto), 0) as total FROM gastos WHERE mes = ? AND categoria = ?",
            (mes, categoria),
        )
        row = await cursor.fetchone()
        return row["total"]

    async def top_comercios(self, mes: str | None = None, limit: int = 10) -> list[dict]:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            """SELECT comercio, COUNT(*) as cantidad, SUM(monto) as total
               FROM gastos WHERE mes = ? AND comercio IS NOT NULL AND comercio != ''
               GROUP BY comercio ORDER BY total DESC LIMIT ?""",
            (mes, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def metodo_pago_breakdown(self, mes: str | None = None) -> list[dict]:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            """SELECT metodo_pago, COUNT(*) as cantidad, SUM(monto) as total
               FROM gastos WHERE mes = ? AND metodo_pago IS NOT NULL AND metodo_pago != ''
               GROUP BY metodo_pago ORDER BY total DESC""",
            (mes,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_cuenta(self, cuenta_id: int, mes: str | None = None) -> list[dict]:
        db = await get_db()
        if mes:
            cursor = await db.execute(
                "SELECT * FROM gastos WHERE cuenta_id = ? AND mes = ? ORDER BY fecha DESC",
                (cuenta_id, mes),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM gastos WHERE cuenta_id = ? ORDER BY fecha DESC",
                (cuenta_id,),
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_tarjeta(self, tarjeta_id: int, mes: str | None = None) -> list[dict]:
        db = await get_db()
        if mes:
            cursor = await db.execute(
                "SELECT * FROM gastos WHERE tarjeta_id = ? AND mes = ? ORDER BY fecha DESC",
                (tarjeta_id, mes),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM gastos WHERE tarjeta_id = ? ORDER BY fecha DESC",
                (tarjeta_id,),
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_tarjeta_daterange(self, tarjeta_id: int,
                                        fecha_inicio: str, fecha_fin: str) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM gastos WHERE tarjeta_id = ? AND fecha >= ? AND fecha <= ? ORDER BY fecha DESC",
            (tarjeta_id, fecha_inicio, fecha_fin),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def buscar(self, texto: str, limit: int = 20) -> list[dict]:
        db = await get_db()
        patron = f"%{texto}%"
        cursor = await db.execute(
            """SELECT * FROM gastos
               WHERE descripcion LIKE ? OR comercio LIKE ? OR categoria LIKE ?
               ORDER BY fecha DESC LIMIT ?""",
            (patron, patron, patron, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]
