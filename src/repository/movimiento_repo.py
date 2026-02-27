"""Unified repository for all financial movements (movimientos)."""
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


class MovimientoRepo:
    async def create(self, tipo: str, monto: float, descripcion: str = "",
                     moneda: str = "PEN", monto_cuenta: float = None,
                     categoria: str = None, comercio: str = None,
                     metodo_pago: str = None, fuente: str = "texto",
                     cuenta_id: int = None, cuenta_destino_id: int = None,
                     tarjeta_id: int = None, tarjeta_periodo_id: int = None,
                     deuda_id: int = None, cobro_id: int = None,
                     cuotas: int = 0, monto_destino: float = None,
                     fecha: str = None, mes: str = None, semana: str = None) -> int:
        now = _now()
        fecha = fecha or now.isoformat()
        mes = mes or now.strftime("%Y-%m")
        semana = semana or now.strftime("%Y-W%V")
        mc = monto_cuenta if monto_cuenta is not None else monto
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO movimientos
               (tipo, monto, moneda, monto_cuenta, descripcion, categoria, comercio,
                metodo_pago, fuente, cuenta_id, cuenta_destino_id, tarjeta_id,
                tarjeta_periodo_id, deuda_id, cobro_id, cuotas, monto_destino,
                fecha, mes, semana)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tipo, monto, moneda, mc, descripcion, categoria, comercio,
             metodo_pago, fuente, cuenta_id, cuenta_destino_id, tarjeta_id,
             tarjeta_periodo_id, deuda_id, cobro_id, cuotas, monto_destino,
             fecha, mes, semana),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_by_id(self, mov_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM movimientos WHERE id = ?", (mov_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update(self, mov_id: int, **fields) -> bool:
        if not fields:
            return False
        db = await get_db()
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [mov_id]
        await db.execute(f"UPDATE movimientos SET {sets} WHERE id = ?", values)
        await db.commit()
        return True

    async def delete(self, mov_id: int):
        db = await get_db()
        await db.execute("DELETE FROM movimientos WHERE id = ?", (mov_id,))
        await db.commit()

    async def delete_many(self, ids: list[int]) -> int:
        if not ids:
            return 0
        db = await get_db()
        placeholders = ",".join("?" for _ in ids)
        cursor = await db.execute(
            f"DELETE FROM movimientos WHERE id IN ({placeholders})", ids
        )
        await db.commit()
        return cursor.rowcount

    # --- Queries by type ---

    async def get_by_tipo(self, tipo: str, mes: str | None = None) -> list[dict]:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM movimientos WHERE tipo = ? AND mes = ? ORDER BY fecha DESC",
            (tipo, mes),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_month(self, mes: str | None = None, tipo: str = None) -> list[dict]:
        mes = mes or _mes_actual()
        db = await get_db()
        if tipo:
            cursor = await db.execute(
                "SELECT * FROM movimientos WHERE mes = ? AND tipo = ? ORDER BY fecha DESC",
                (mes, tipo),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM movimientos WHERE mes = ? ORDER BY fecha DESC", (mes,),
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_today(self, tipo: str = None) -> list[dict]:
        inicio = _inicio_hoy()
        db = await get_db()
        if tipo:
            cursor = await db.execute(
                "SELECT * FROM movimientos WHERE fecha >= ? AND tipo = ? ORDER BY fecha DESC",
                (inicio, tipo),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM movimientos WHERE fecha >= ? ORDER BY fecha DESC", (inicio,),
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_gastos_hoy(self) -> list[dict]:
        return await self.get_today(tipo="gasto")

    async def get_ingresos_mes(self, mes: str | None = None) -> list[dict]:
        return await self.get_by_tipo("ingreso", mes)

    # --- Cuenta/Tarjeta queries ---

    async def get_by_cuenta(self, cuenta_id: int, mes: str = None,
                            tipo: str = None) -> list[dict]:
        db = await get_db()
        q = "SELECT * FROM movimientos WHERE (cuenta_id = ? OR cuenta_destino_id = ?)"
        params: list = [cuenta_id, cuenta_id]
        if mes:
            q += " AND mes = ?"
            params.append(mes)
        if tipo:
            q += " AND tipo = ?"
            params.append(tipo)
        q += " ORDER BY fecha DESC"
        cursor = await db.execute(q, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_tarjeta(self, tarjeta_id: int, mes: str = None) -> list[dict]:
        db = await get_db()
        q = "SELECT * FROM movimientos WHERE tarjeta_id = ?"
        params: list = [tarjeta_id]
        if mes:
            q += " AND mes = ?"
            params.append(mes)
        q += " ORDER BY fecha DESC"
        cursor = await db.execute(q, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_tarjeta_daterange(self, tarjeta_id: int,
                                       fecha_inicio: str, fecha_fin: str) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """SELECT * FROM movimientos
               WHERE tarjeta_id = ? AND fecha >= ? AND fecha <= ?
               ORDER BY fecha DESC""",
            (tarjeta_id, fecha_inicio, fecha_fin),
        )
        return [dict(r) for r in await cursor.fetchall()]

    # --- Summaries ---

    async def resumen_hoy(self) -> str:
        gastos = await self.get_gastos_hoy()
        if not gastos:
            return "Hoy no has registrado gastos."
        total = sum(g["monto"] for g in gastos)
        lines = [f"Gastos de hoy ({len(gastos)}):"]
        by_cat: dict[str, float] = {}
        for g in gastos:
            cat = g.get("categoria") or "otros"
            by_cat[cat] = by_cat.get(cat, 0) + g["monto"]
        for cat, monto in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  | {cat.title()}: S/{monto:.2f}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)

    async def resumen_semana(self) -> str:
        semana = _semana_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM movimientos WHERE semana = ? AND tipo = 'gasto'", (semana,)
        )
        gastos = [dict(r) for r in await cursor.fetchall()]
        if not gastos:
            return "Esta semana no hay gastos registrados."
        total = sum(g["monto"] for g in gastos)
        lines = [f"Gastos de la semana ({len(gastos)}):"]
        by_cat: dict[str, float] = {}
        for g in gastos:
            cat = g.get("categoria") or "otros"
            by_cat[cat] = by_cat.get(cat, 0) + g["monto"]
        for cat, monto in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  | {cat.title()}: S/{monto:.2f}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)

    async def resumen_mes(self) -> str:
        gastos = await self.get_by_tipo("gasto")
        if not gastos:
            return "Este mes no hay gastos registrados."
        total = sum(g["monto"] for g in gastos)
        lines = [f"Gastos del mes ({len(gastos)}):"]
        by_cat: dict[str, float] = {}
        for g in gastos:
            cat = g.get("categoria") or "otros"
            by_cat[cat] = by_cat.get(cat, 0) + g["monto"]
        for cat, monto in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  | {cat.title()}: S/{monto:.2f}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)

    async def resumen_categorias(self, mes: str | None = None) -> dict:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT categoria, SUM(monto) as total FROM movimientos WHERE mes = ? AND tipo = 'gasto' GROUP BY categoria",
            (mes,),
        )
        return {row["categoria"]: row["total"] for row in await cursor.fetchall()}

    async def total_categoria_mes(self, categoria: str, mes: str | None = None) -> float:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            "SELECT COALESCE(SUM(monto), 0) as total FROM movimientos WHERE mes = ? AND tipo = 'gasto' AND categoria = ?",
            (mes, categoria),
        )
        row = await cursor.fetchone()
        return row["total"]

    async def top_comercios(self, mes: str | None = None, limit: int = 10) -> list[dict]:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            """SELECT comercio, COUNT(*) as cantidad, SUM(monto) as total
               FROM movimientos WHERE mes = ? AND tipo = 'gasto'
               AND comercio IS NOT NULL AND comercio != ''
               GROUP BY comercio ORDER BY total DESC LIMIT ?""",
            (mes, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def metodo_pago_breakdown(self, mes: str | None = None) -> list[dict]:
        mes = mes or _mes_actual()
        db = await get_db()
        cursor = await db.execute(
            """SELECT metodo_pago, COUNT(*) as cantidad, SUM(monto) as total
               FROM movimientos WHERE mes = ? AND tipo = 'gasto'
               AND metodo_pago IS NOT NULL AND metodo_pago != ''
               GROUP BY metodo_pago ORDER BY total DESC""",
            (mes,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    # --- Search ---

    async def buscar(self, texto: str, tipo: str = None, limit: int = 20) -> list[dict]:
        db = await get_db()
        patron = f"%{texto}%"
        if tipo:
            cursor = await db.execute(
                """SELECT * FROM movimientos
                   WHERE tipo = ? AND (descripcion LIKE ? OR comercio LIKE ? OR categoria LIKE ?)
                   ORDER BY fecha DESC LIMIT ?""",
                (tipo, patron, patron, patron, limit),
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM movimientos
                   WHERE descripcion LIKE ? OR comercio LIKE ? OR categoria LIKE ?
                   ORDER BY fecha DESC LIMIT ?""",
                (patron, patron, patron, limit),
            )
        return [dict(r) for r in await cursor.fetchall()]

    # --- Bulk import ---

    async def bulk_create(self, movimientos: list[dict]) -> list[int]:
        """Create multiple movimientos in a single transaction."""
        db = await get_db()
        ids = []
        for m in movimientos:
            now = _now()
            fecha = m.get("fecha") or now.isoformat()
            mes = m.get("mes") or now.strftime("%Y-%m")
            semana = m.get("semana") or now.strftime("%Y-W%V")
            mc = m.get("monto_cuenta") if m.get("monto_cuenta") is not None else m["monto"]
            cursor = await db.execute(
                """INSERT INTO movimientos
                   (tipo, monto, moneda, monto_cuenta, descripcion, categoria, comercio,
                    metodo_pago, fuente, cuenta_id, cuenta_destino_id, tarjeta_id,
                    tarjeta_periodo_id, deuda_id, cobro_id, cuotas, monto_destino,
                    fecha, mes, semana)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (m.get("tipo", "gasto"), m["monto"], m.get("moneda", "PEN"), mc,
                 m.get("descripcion", ""), m.get("categoria"), m.get("comercio"),
                 m.get("metodo_pago"), m.get("fuente", "importacion"),
                 m.get("cuenta_id"), m.get("cuenta_destino_id"), m.get("tarjeta_id"),
                 m.get("tarjeta_periodo_id"), m.get("deuda_id"), m.get("cobro_id"),
                 m.get("cuotas", 0), m.get("monto_destino"),
                 fecha, mes, semana),
            )
            ids.append(cursor.lastrowid)
        await db.commit()
        return ids
