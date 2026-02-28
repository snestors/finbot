import logging
from src.database.db import get_db

logger = logging.getLogger(__name__)


class GoogleEmailRepo:

    async def save(self, message_id: str, thread_id: str, from_addr: str,
                   subject: str, snippet: str, date_received: str,
                   clasificacion: str = "otro", accion: str = None) -> int:
        db = await get_db()
        cursor = await db.execute(
            """INSERT OR IGNORE INTO google_emails
               (message_id, thread_id, from_addr, subject, snippet,
                date_received, clasificacion, accion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (message_id, thread_id, from_addr, subject, snippet,
             date_received, clasificacion, accion),
        )
        await db.commit()
        return cursor.lastrowid

    async def exists(self, message_id: str) -> bool:
        db = await get_db()
        cursor = await db.execute(
            "SELECT 1 FROM google_emails WHERE message_id = ?",
            (message_id,),
        )
        return await cursor.fetchone() is not None

    async def get_since(self, fecha_iso: str) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """SELECT * FROM google_emails
               WHERE date_received >= ?
               ORDER BY date_received DESC""",
            (fecha_iso,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def mark_notified(self, email_id: int):
        db = await get_db()
        await db.execute(
            "UPDATE google_emails SET notificado = 1 WHERE id = ?",
            (email_id,),
        )
        await db.commit()
