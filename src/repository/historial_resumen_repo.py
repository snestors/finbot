from src.database.db import get_db


class HistorialResumenRepo:
    async def get_latest(self) -> dict | None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM historial_resumenes ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "summary": row["summary"],
            "desde_id": row["desde_id"],
            "hasta_id": row["hasta_id"],
            "msg_count": row["msg_count"],
            "created_at": row["created_at"],
        }

    async def create(self, summary: str, desde_id: int, hasta_id: int, msg_count: int) -> dict:
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO historial_resumenes (summary, desde_id, hasta_id, msg_count)
               VALUES (?, ?, ?, ?)""",
            (summary, desde_id, hasta_id, msg_count),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "summary": summary,
            "desde_id": desde_id,
            "hasta_id": hasta_id,
            "msg_count": msg_count,
        }
