import logging

from src.database.db import get_db

logger = logging.getLogger(__name__)


class ConsumoConfigRepo:

    async def get(self, clave: str) -> str | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT valor FROM consumo_config WHERE clave = ?", (clave,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def get_float(self, clave: str, default: float = 0.0) -> float:
        val = await self.get(clave)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    async def set(self, clave: str, valor: str):
        db = await get_db()
        await db.execute(
            """INSERT INTO consumo_config (clave, valor, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, updated_at = datetime('now')""",
            (clave, valor),
        )
        await db.commit()

    async def get_all(self) -> dict:
        db = await get_db()
        cursor = await db.execute("SELECT clave, valor FROM consumo_config")
        return {r[0]: r[1] for r in await cursor.fetchall()}
