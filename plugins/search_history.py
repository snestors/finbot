"""
Plugin: search_history
Búsqueda de texto libre en el historial de conversaciones usando SQLite FTS5.

El índice FTS5 se crea automáticamente en la primera búsqueda y se mantiene
sincronizado incrementalmente (rowid = mensajes.id).
"""
import sqlite3
import re
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "finbot.db"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_fts(conn):
    """Create FTS5 virtual table and index any new messages."""
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS mensajes_fts
        USING fts5(content, tokenize='unicode61 remove_diacritics 2')
    """)

    last_id = conn.execute("SELECT MAX(rowid) FROM mensajes_fts").fetchone()[0] or 0

    new = conn.execute(
        "SELECT id, content FROM mensajes WHERE id > ? AND content != '' ORDER BY id",
        (last_id,),
    ).fetchall()

    if new:
        conn.executemany(
            "INSERT INTO mensajes_fts(rowid, content) VALUES (?, ?)",
            [(r["id"], r["content"]) for r in new],
        )
        conn.commit()


def _safe_fts_query(query: str) -> str:
    """Escape special FTS5 chars so arbitrary user input doesn't break MATCH."""
    words = query.split()
    cleaned = []
    for w in words:
        w = re.sub(r'["\*\-\+\(\)\{\}\[\]\^~:]', " ", w).strip()
        if w:
            cleaned.append(f'"{w}"')
    if not cleaned:
        return f'"{query}"'
    if len(cleaned) == 1:
        return cleaned[0] + "*"          # prefix match for single word
    return " ".join(cleaned)             # AND semantics for multiple words


def search_history(params: dict) -> str:
    """Search conversation history by free text."""
    query = (params.get("query") or "").strip()
    if not query:
        return "Error: se requiere el parámetro 'query'"

    limit = min(int(params.get("limit", 20)), 50)
    conn = _get_conn()

    try:
        _ensure_fts(conn)
        fts_q = _safe_fts_query(query)

        results = conn.execute(
            """
            SELECT
                m.id,
                m.role,
                m.timestamp,
                snippet(mensajes_fts, 0, '**', '**', '...', 48) AS excerpt
            FROM mensajes_fts
            JOIN mensajes m ON m.id = mensajes_fts.rowid
            WHERE mensajes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_q, limit),
        ).fetchall()

        # Fallback to LIKE if FTS returned nothing (e.g. partial word not matched)
        if not results:
            results = conn.execute(
                """
                SELECT id, role, timestamp, content AS excerpt
                FROM mensajes
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            ).fetchall()

        if not results:
            return f"No encontré mensajes con: '{query}'"

        lines = [f"Encontré {len(results)} resultado(s) para '{query}':\n"]
        for r in results:
            ts = (r["timestamp"] or "?")[:16]
            role = "Tú" if r["role"] == "user" else "KYN3D"
            excerpt = (r["excerpt"] or "")[:300]
            lines.append(f"[{ts}] {role}: {excerpt}\n")

        return "\n".join(lines)

    except Exception as e:
        return f"Error buscando: {e}"
    finally:
        conn.close()


def rebuild_index(params: dict) -> str:
    """Drop and recreate the FTS5 index from scratch."""
    conn = _get_conn()
    try:
        conn.execute("DROP TABLE IF EXISTS mensajes_fts")
        conn.commit()
        _ensure_fts(conn)
        count = conn.execute("SELECT COUNT(*) FROM mensajes_fts").fetchone()[0]
        return f"Índice reconstruido: {count} mensajes indexados."
    except Exception as e:
        return f"Error reconstruyendo índice: {e}"
    finally:
        conn.close()


def register():
    return {
        "tools": {
            "search_history": {
                "description": (
                    "Busca en el historial de conversaciones por texto libre. "
                    "Usa esto cuando el usuario pregunte por algo que se habló antes, "
                    "temas pasados, o quiera recuperar información de conversaciones anteriores. "
                    "Params: query (str, requerido), limit (int, default 20, max 50)"
                ),
                "handler": search_history,
            },
            "rebuild_search_index": {
                "description": "Reconstruye el índice de búsqueda de historial desde cero.",
                "handler": rebuild_index,
            },
        }
    }
