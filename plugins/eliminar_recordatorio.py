"""Plugin: eliminar_recordatorio action handler."""
import logging

logger = logging.getLogger(__name__)


def register():
    return {
        "tools": {},
        "actions": {
            "eliminar_recordatorio": _handle_eliminar_recordatorio,
        },
    }


async def _handle_eliminar_recordatorio(accion: dict, repos: dict) -> dict:
    recordatorio_id = accion.get("recordatorio_id")
    if not recordatorio_id:
        return {"data_response": "Error: falta recordatorio_id"}
    recordatorio_repo = repos.get("recordatorio")
    if not recordatorio_repo:
        return {"data_response": "Error: repo de recordatorios no disponible"}
    try:
        await recordatorio_repo.delete(recordatorio_id)
        return {"data_response": f"Recordatorio #{recordatorio_id} eliminado."}
    except Exception as e:
        logger.error(f"Error eliminando recordatorio {recordatorio_id}: {e}")
        return {"data_response": f"Error: {e}"}
