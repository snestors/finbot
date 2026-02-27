from src.database.db import get_db


class MemoriaRepo:
    async def save(self, categoria: str, clave: str, valor: str, confianza: float = 1.0):
        db = await get_db()
        await db.execute(
            """INSERT INTO memoria (categoria, clave, valor, confianza)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(categoria, clave) DO UPDATE SET
                 valor = excluded.valor,
                 confianza = MIN(confianza + 0.2, 2.0),
                 veces_confirmado = veces_confirmado + 1,
                 updated_at = datetime('now')""",
            (categoria, clave, valor, confianza),
        )
        await db.commit()

    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM memoria ORDER BY confianza DESC, updated_at DESC"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_categoria(self, categoria: str) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM memoria WHERE categoria = ? ORDER BY confianza DESC",
            (categoria,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def delete(self, memoria_id: int):
        db = await get_db()
        await db.execute("DELETE FROM memoria WHERE id = ?", (memoria_id,))
        await db.commit()

    async def format_for_context(self) -> str:
        memorias = await self.get_all()
        if not memorias:
            return ""
        lines = []
        by_cat: dict[str, list[str]] = {}
        for m in memorias:
            cat = m["categoria"]
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(f"{m['clave']}: {m['valor']}")
        for cat, items in by_cat.items():
            lines.append(f"  [{cat}]")
            for item in items:
                lines.append(f"    - {item}")
        return "Memoria persistente:\n" + "\n".join(lines)
