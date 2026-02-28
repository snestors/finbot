"""History compaction: summarize old messages to keep context manageable."""
import logging

from src.llm import LLMClient
from src.repository.mensaje_repo import MensajeRepo
from src.repository.historial_resumen_repo import HistorialResumenRepo

logger = logging.getLogger(__name__)

COMPACTION_PROMPT = """Eres un asistente que resume conversaciones financieras.
Genera un resumen estructurado y conciso de la siguiente conversación.
El resumen debe preservar información clave para que el bot pueda continuar la conversación con contexto.

Formato del resumen:

### Transacciones registradas
- (lista con IDs, montos, categorías, descripciones breves)

### Transacciones eliminadas o modificadas
- (si hubo alguna)

### Consultas y respuestas clave
- (preguntas del usuario y respuestas importantes)

### Correcciones hechas
- (errores corregidos durante la conversación)

### Decisiones y acuerdos
- (cualquier preferencia o decisión tomada)

### Contexto importante
- (información relevante para futuras interacciones)

Si una sección no tiene contenido, omítela. Sé conciso pero no pierdas información financiera importante (montos, IDs, cuentas, tarjetas).
"""


class HistoryCompactor:
    def __init__(self, llm: LLMClient, mensaje_repo: MensajeRepo,
                 resumen_repo: HistorialResumenRepo):
        self.llm = llm
        self.mensaje_repo = mensaje_repo
        self.resumen_repo = resumen_repo

    async def maybe_compact(self, threshold: int = 60, raw_window: int = 20):
        """Compact old messages if uncompacted count exceeds threshold."""
        try:
            total = await self.mensaje_repo.count_uncompacted()
            if total <= threshold:
                logger.info(f"[compactor] {total} uncompacted, threshold={threshold}, skip")
                return

            # Messages to summarize = everything except the raw_window
            to_summarize = total - raw_window
            if to_summarize <= 0:
                return

            logger.info(f"[compactor] {total} uncompacted (threshold={threshold}), "
                        f"compacting {to_summarize} oldest messages")

            old_msgs = await self.mensaje_repo.get_oldest_uncompacted(to_summarize)
            if not old_msgs:
                return

            # Build conversation text for the LLM
            prev_summary = await self.resumen_repo.get_latest()
            conversation = self._format_conversation(old_msgs, prev_summary)

            # Generate summary via LLM
            llm_response = await self.llm.generate(
                system=COMPACTION_PROMPT,
                user_message=conversation,
                caller="compactor",
            )
            summary = llm_response.text.strip()

            # Save summary and mark messages as compacted
            desde_id = old_msgs[0]["id"]
            hasta_id = old_msgs[-1]["id"]
            await self.resumen_repo.create(
                summary=summary,
                desde_id=desde_id,
                hasta_id=hasta_id,
                msg_count=len(old_msgs),
            )
            await self.mensaje_repo.mark_compacted(desde_id, hasta_id)

            logger.info(f"[compactor] Compacted {len(old_msgs)} messages "
                        f"(ids {desde_id}-{hasta_id}), summary length={len(summary)}")

        except Exception as e:
            logger.error(f"[compactor] Error during compaction: {e}", exc_info=True)

    def _format_conversation(self, messages: list[dict],
                             prev_summary: dict | None) -> str:
        parts = []
        if prev_summary:
            parts.append("## RESUMEN ANTERIOR DE LA CONVERSACION")
            parts.append(prev_summary["summary"])
            parts.append("")

        parts.append("## MENSAJES A RESUMIR")
        for msg in messages:
            role = "Usuario" if msg["role"] == "user" else "Bot"
            content = msg.get("content", "")
            if not content:
                continue
            # Truncate very long messages
            if len(content) > 1000:
                content = content[:700] + "\n...(truncado)...\n" + content[-200:]
            parts.append(f"[{role}] {content}")

        return "\n".join(parts)
