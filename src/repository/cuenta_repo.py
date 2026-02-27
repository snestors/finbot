import json
from src.database.db import get_db


_SALDO_QUERY = """
SELECT COALESCE(c.saldo_inicial, 0)
  + COALESCE((SELECT SUM(monto_cuenta) FROM movimientos WHERE cuenta_id = c.id AND tipo = 'ingreso'), 0)
  + COALESCE((SELECT SUM(monto_cuenta) FROM movimientos WHERE cuenta_id = c.id AND tipo = 'pago_cobro'), 0)
  - COALESCE((SELECT SUM(monto_cuenta) FROM movimientos WHERE cuenta_id = c.id AND tipo = 'gasto'), 0)
  - COALESCE((SELECT SUM(monto_cuenta) FROM movimientos WHERE cuenta_id = c.id AND tipo = 'pago_deuda'), 0)
  - COALESCE((SELECT SUM(monto_cuenta) FROM movimientos WHERE cuenta_id = c.id AND tipo = 'pago_tarjeta'), 0)
  + COALESCE((SELECT SUM(monto_destino) FROM movimientos WHERE cuenta_destino_id = c.id AND tipo = 'transferencia'), 0)
  - COALESCE((SELECT SUM(monto_cuenta) FROM movimientos WHERE cuenta_id = c.id AND tipo = 'transferencia'), 0)
AS saldo
FROM cuentas c WHERE c.id = ?
"""


class CuentaRepo:
    async def calcular_saldo(self, cuenta_id: int) -> float:
        db = await get_db()
        cursor = await db.execute(_SALDO_QUERY, (cuenta_id,))
        row = await cursor.fetchone()
        return round(row[0], 2) if row and row[0] else 0.0

    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM cuentas WHERE activa = 1 ORDER BY nombre")
        cuentas = [dict(r) for r in await cursor.fetchall()]
        for c in cuentas:
            c["saldo"] = await self.calcular_saldo(c["id"])
            c["metodos_pago"] = _parse_metodos(c.get("metodos_pago"))
        return cuentas

    async def get_by_id(self, cuenta_id: int) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM cuentas WHERE id = ?", (cuenta_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        c = dict(row)
        c["saldo"] = await self.calcular_saldo(c["id"])
        c["metodos_pago"] = _parse_metodos(c.get("metodos_pago"))
        return c

    async def get_by_metodo_pago(self, metodo: str) -> dict | None:
        """Find account linked to a payment method (yape, plin, etc)."""
        db = await get_db()
        cursor = await db.execute("SELECT * FROM cuentas WHERE activa = 1")
        for row in await cursor.fetchall():
            c = dict(row)
            metodos = _parse_metodos(c.get("metodos_pago"))
            if metodo.lower() in [m.lower() for m in metodos]:
                c["saldo"] = await self.calcular_saldo(c["id"])
                c["metodos_pago"] = metodos
                return c
        return None

    async def save(self, data: dict) -> int:
        db = await get_db()
        cuenta_id = data.get("id")
        metodos = json.dumps(data.get("metodos_pago", []))
        if cuenta_id:
            await db.execute(
                """UPDATE cuentas SET nombre=?, tipo=?, moneda=?, saldo_inicial=?,
                   metodos_pago=?, color=?, activa=? WHERE id=?""",
                (
                    data["nombre"], data.get("tipo", "efectivo"),
                    data.get("moneda", "PEN"), data.get("saldo_inicial", 0),
                    metodos, data.get("color", "#00f0ff"),
                    1 if data.get("activa", True) else 0,
                    cuenta_id,
                ),
            )
        else:
            cursor = await db.execute(
                """INSERT INTO cuentas (nombre, tipo, moneda, saldo_inicial, metodos_pago, color, activa)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["nombre"], data.get("tipo", "efectivo"),
                    data.get("moneda", "PEN"), data.get("saldo_inicial", 0),
                    metodos, data.get("color", "#00f0ff"), 1,
                ),
            )
            cuenta_id = cursor.lastrowid
        await db.commit()
        return cuenta_id

    async def delete(self, cuenta_id: int):
        db = await get_db()
        await db.execute("UPDATE cuentas SET activa = 0 WHERE id = ?", (cuenta_id,))
        await db.commit()


def _parse_metodos(val) -> list[str]:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []
