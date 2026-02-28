"""Plugin: actualizar_recordatorio — update an existing reminder's fields."""
import logging

logger = logging.getLogger(__name__)


def register():
    return {
        "tools": {},
        "actions": {
            "actualizar_recordatorio": _handle_actualizar_recordatorio,
        },
    }


async def _handle_actualizar_recordatorio(accion: dict, repos: dict) -> dict:
    recordatorio_id = accion.get("recordatorio_id")
    if not recordatorio_id:
        return {"data_response": "Error: falta recordatorio_id"}

    recordatorio_repo = repos.get("recordatorio")
    if not recordatorio_repo:
        return {"data_response": "Error: repo de recordatorios no disponible"}

    existing = await recordatorio_repo.get_by_id(recordatorio_id)
    if not existing:
        return {"data_response": f"Error: recordatorio #{recordatorio_id} no encontrado"}

    # Build update fields
    updates = {}
    for field in ("mensaje", "hora", "dias"):
        if field in accion:
            updates[field] = accion[field]

    if not updates:
        return {"data_response": "Error: no hay campos para actualizar (usa mensaje, hora, dias)"}

    try:
        from src.database.db import get_db
        db = await get_db()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [recordatorio_id]
        await db.execute(
            f"UPDATE recordatorios SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

        changes = ", ".join(f"{k}={v}" for k, v in updates.items())
        return {"data_response": f"Recordatorio #{recordatorio_id} actualizado: {changes}"}
    except Exception as e:
        logger.error(f"Error actualizando recordatorio {recordatorio_id}: {e}")
        return {"data_response": f"Error: {e}"}
