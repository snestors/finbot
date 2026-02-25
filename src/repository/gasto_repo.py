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
    async def create(self, monto: float, categoria: str, descripcion: str, fuente: str) -> int:
        now = _now()
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO gastos (monto, categoria, descripcion, fuente, fecha, mes, semana)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (monto, categoria, descripcion, fuente,
             now.isoformat(), now.strftime("%Y-%m"), now.strftime("%Y-W%V")),
        )
        await db.commit()
        return cursor.lastrowid

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
