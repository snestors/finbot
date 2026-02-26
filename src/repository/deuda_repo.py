from datetime import datetime
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


class DeudaRepo:
    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM deudas WHERE activa = 1")
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["pagos"] = await self._get_pagos(d["id"])
            result.append(d)
        return result

    async def get_by_id(self, deuda_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM deudas WHERE id = ?", (deuda_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["pagos"] = await self._get_pagos(d["id"])
        return d

    async def save(self, data: dict) -> int:
        db = await get_db()
        deuda_id = data.get("id")
        if deuda_id:
            await db.execute(
                """UPDATE deudas SET nombre=?, saldo_actual=?, tasa_interes_mensual=?,
                   pago_minimo=?, fecha_corte=?, fecha_pago=?, activa=?,
                   entidad=?, cuotas_total=?, cuotas_pagadas=?, cuota_monto=?
                   WHERE id=?""",
                (
                    data["nombre"], data.get("saldo_actual", 0),
                    data.get("tasa_interes_mensual", 0), data.get("pago_minimo", 0),
                    data.get("fecha_corte", 0), data.get("fecha_pago", 0),
                    1 if data.get("activa", True) else 0,
                    data.get("entidad"), data.get("cuotas_total", 0),
                    data.get("cuotas_pagadas", 0), data.get("cuota_monto", 0),
                    deuda_id,
                ),
            )
        else:
            cursor = await db.execute(
                """INSERT INTO deudas (nombre, saldo_actual, tasa_interes_mensual,
                   pago_minimo, fecha_corte, fecha_pago, activa,
                   entidad, cuotas_total, cuotas_pagadas, cuota_monto)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["nombre"], data.get("saldo_actual", 0),
                    data.get("tasa_interes_mensual", 0), data.get("pago_minimo", 0),
                    data.get("fecha_corte", 0), data.get("fecha_pago", 0), 1,
                    data.get("entidad"), data.get("cuotas_total", 0),
                    data.get("cuotas_pagadas", 0), data.get("cuota_monto", 0),
                ),
            )
            deuda_id = cursor.lastrowid
        await db.commit()
        return deuda_id

    async def registrar_pago(self, deuda_id: int, monto: float):
        db = await get_db()
        cursor = await db.execute("SELECT * FROM deudas WHERE id = ?", (deuda_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Deuda {deuda_id} no encontrada")

        deuda = dict(row)
        nuevo_saldo = max(0, deuda["saldo_actual"] - monto)
        activa = 1 if nuevo_saldo > 0 else 0
        cuotas_pagadas = deuda.get("cuotas_pagadas", 0) or 0

        if deuda.get("cuotas_total", 0) and deuda.get("cuotas_total", 0) > 0:
            cuotas_pagadas += 1

        await db.execute(
            "UPDATE deudas SET saldo_actual = ?, activa = ?, cuotas_pagadas = ? WHERE id = ?",
            (nuevo_saldo, activa, cuotas_pagadas, deuda_id),
        )
        await db.execute(
            "INSERT INTO deuda_pagos (deuda_id, monto, fecha) VALUES (?, ?, ?)",
            (deuda_id, monto, _now().isoformat()),
        )
        await db.commit()

    async def resumen(self) -> str:
        deudas = await self.get_all()
        if not deudas:
            return "No tienes deudas activas."
        total = sum(d["saldo_actual"] for d in deudas)
        lines = [f"Deudas activas ({len(deudas)}):"]
        for d in deudas:
            entidad = f" ({d['entidad']})" if d.get("entidad") else ""
            cuotas = ""
            if d.get("cuotas_total") and d["cuotas_total"] > 0:
                cuotas = f" [{d.get('cuotas_pagadas', 0)}/{d['cuotas_total']} cuotas]"
            lines.append(f"  | {d['nombre']}{entidad}: S/{d['saldo_actual']:.2f}{cuotas}")
        lines.append(f"  Total: S/{total:.2f}")
        return "\n".join(lines)

    async def _get_pagos(self, deuda_id: int) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM deuda_pagos WHERE deuda_id = ? ORDER BY fecha DESC",
            (deuda_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]
