from datetime import datetime
from zoneinfo import ZoneInfo
from src.database.db import get_db
from src.config import settings


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


class PerfilRepo:
    async def get(self) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM perfil_usuario LIMIT 1")
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_or_update(self, data: dict) -> dict:
        db = await get_db()
        existing = await self.get()
        if existing:
            fields = []
            values = []
            for key in ("nombre", "moneda_default", "onboarding_completo"):
                if key in data:
                    fields.append(f"{key} = ?")
                    values.append(data[key])
            if fields:
                values.append(existing["id"])
                await db.execute(
                    f"UPDATE perfil_usuario SET {', '.join(fields)} WHERE id = ?",
                    values,
                )
                await db.commit()
            return {**existing, **data}
        else:
            now = _now().isoformat()
            await db.execute(
                """INSERT INTO perfil_usuario (nombre, moneda_default, onboarding_completo, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    data.get("nombre"),
                    data.get("moneda_default", "PEN"),
                    1 if data.get("onboarding_completo") else 0,
                    now,
                ),
            )
            await db.commit()
            return await self.get()

    async def is_onboarding_complete(self) -> bool:
        perfil = await self.get()
        if not perfil:
            return False
        return bool(perfil.get("onboarding_completo"))
