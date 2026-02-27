import json
from src.database.db import get_db


class MensajeRepo:
    async def save(self, data: dict) -> dict:
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO mensajes (role, content, media_path, source, timestamp, gasto_ids, model)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["role"],
                data.get("content", ""),
                data.get("media_path"),
                data["source"],
                data["timestamp"],
                json.dumps(data.get("gastoIds", [])),
                data.get("model"),
            ),
        )
        await db.commit()
        data["id"] = cursor.lastrowid
        return data

    async def get_history(self, limit: int = 50, before: int | None = None) -> list[dict]:
        db = await get_db()
        if before:
            cursor = await db.execute(
                """SELECT * FROM mensajes WHERE id < ? ORDER BY id DESC LIMIT ?""",
                (before, limit),
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM mensajes ORDER BY id DESC LIMIT ?""",
                (limit,),
            )
        rows = await cursor.fetchall()
        results = [self._row_to_dict(r) for r in rows]
        results.reverse()
        return results

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "media_path": row["media_path"],
            "source": row["source"],
            "timestamp": row["timestamp"],
            "gastoIds": json.loads(row["gasto_ids"]),
        }
