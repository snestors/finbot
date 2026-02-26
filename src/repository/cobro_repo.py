"""Repository for cuentas por cobrar (accounts receivable)."""
import logging
from src.database.db import get_db

logger = logging.getLogger(__name__)


class CobroRepo:
    async def get_all(self, solo_pendientes: bool = True) -> list[dict]:
        db = await get_db()
        if solo_pendientes:
            rows = await db.execute_fetchall(
                "SELECT * FROM cobros WHERE saldo_pendiente > 0 ORDER BY created_at DESC"
            )
        else:
            rows = await db.execute_fetchall("SELECT * FROM cobros ORDER BY created_at DESC")
        return [dict(r) for r in rows]

    async def save(self, data: dict) -> int:
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO cobros (deudor, concepto, monto_total, saldo_pendiente, moneda)
               VALUES (?, ?, ?, ?, ?)""",
            (data["deudor"], data.get("concepto", ""),
             data["monto_total"], data["monto_total"],
             data.get("moneda", "PEN"))
        )
        await db.commit()
        return cursor.lastrowid

    async def registrar_pago(self, cobro_id: int, monto: float) -> dict:
        db = await get_db()
        await db.execute(
            "UPDATE cobros SET saldo_pendiente = MAX(0, saldo_pendiente - ?) WHERE id = ?",
            (monto, cobro_id)
        )
        await db.execute(
            "INSERT INTO cobro_pagos (cobro_id, monto) VALUES (?, ?)",
            (cobro_id, monto)
        )
        await db.commit()
        row = await db.execute_fetchone("SELECT * FROM cobros WHERE id = ?", (cobro_id,))
        return dict(row) if row else {}

    async def get_by_deudor(self, nombre: str) -> list[dict]:
        db = await get_db()
        rows = await db.execute_fetchall(
            "SELECT * FROM cobros WHERE LOWER(deudor) LIKE ? AND saldo_pendiente > 0",
            (f"%{nombre.lower()}%",)
        )
        return [dict(r) for r in rows]

    async def resumen(self) -> str:
        db = await get_db()
        rows = await db.execute_fetchall(
            "SELECT * FROM cobros WHERE saldo_pendiente > 0 ORDER BY saldo_pendiente DESC"
        )
        if not rows:
            return "No tienes cuentas por cobrar pendientes."
        lines = ["Cuentas por cobrar:"]
        total = 0
        for r in rows:
            r = dict(r)
            lines.append(f"  | {r['deudor']}: S/{r['saldo_pendiente']:.2f} de S/{r['monto_total']:.2f} ({r.get('concepto', '')})")
            total += r["saldo_pendiente"]
        lines.append(f"  Total por cobrar: S/{total:.2f}")
        return "\n".join(lines)

    async def delete(self, cobro_id: int):
        db = await get_db()
        await db.execute("DELETE FROM cobros WHERE id = ?", (cobro_id,))
        await db.commit()
