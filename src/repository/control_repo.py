import logging
import re

from src.database.db import get_db

logger = logging.getLogger(__name__)


class ControlRepo:

    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM controls ORDER BY sort_order")
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_id(self, control_id: str) -> dict | None:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM controls WHERE id = ?", (control_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create(self, data: dict) -> str:
        db = await get_db()
        name = data.get("name", "").strip()
        control_id = data.get("id") or self._slugify(name)
        # Ensure unique id
        existing = await self.get_by_id(control_id)
        if existing:
            suffix = 2
            while await self.get_by_id(f"{control_id}_{suffix}"):
                suffix += 1
            control_id = f"{control_id}_{suffix}"
        # Default sort_order = max + 1
        cursor = await db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM controls")
        next_order = (await cursor.fetchone())[0]
        await db.execute(
            """INSERT INTO controls (id, name, icon_name, color_hex, is_active, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                control_id,
                name,
                data.get("icon_name", "lightbulb"),
                data.get("color_hex", "#F59E0B"),
                1 if data.get("is_active") else 0,
                data.get("sort_order", next_order),
            ),
        )
        await db.commit()
        return control_id

    async def update(self, control_id: str, data: dict) -> bool:
        db = await get_db()
        existing = await self.get_by_id(control_id)
        if not existing:
            return False
        fields = []
        values = []
        for col in ("name", "icon_name", "color_hex", "is_active", "sort_order"):
            if col in data:
                fields.append(f"{col} = ?")
                val = data[col]
                if col == "is_active":
                    val = 1 if val else 0
                values.append(val)
        if not fields:
            return True
        values.append(control_id)
        await db.execute(
            f"UPDATE controls SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await db.commit()
        return True

    async def delete(self, control_id: str) -> bool:
        db = await get_db()
        cursor = await db.execute("DELETE FROM controls WHERE id = ?", (control_id,))
        await db.commit()
        return cursor.rowcount > 0

    async def toggle(self, control_id: str) -> dict | None:
        db = await get_db()
        existing = await self.get_by_id(control_id)
        if not existing:
            return None
        new_state = 0 if existing["is_active"] else 1
        await db.execute(
            "UPDATE controls SET is_active = ? WHERE id = ?",
            (new_state, control_id),
        )
        await db.commit()
        return await self.get_by_id(control_id)

    async def reorder(self, ids: list[str]) -> bool:
        db = await get_db()
        for idx, control_id in enumerate(ids):
            await db.execute(
                "UPDATE controls SET sort_order = ? WHERE id = ?",
                (idx, control_id),
            )
        await db.commit()
        return True

    @staticmethod
    def _slugify(name: str) -> str:
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s-]+", "_", slug)
        return slug
