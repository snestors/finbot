import base64
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from src.config import settings

logger = logging.getLogger(__name__)

RECEIPTS_DIR = Path(settings.receipts_dir)


class MessageBus:
    def __init__(self, mensaje_repo, processor, whatsapp, ws_manager):
        self.mensaje_repo = mensaje_repo
        self.processor = processor
        self.whatsapp = whatsapp
        self.ws_manager = ws_manager
        # Give processor a reference back so it can send follow-up messages
        self.processor._message_bus = self

    def _now_iso(self) -> str:
        return datetime.now(ZoneInfo(settings.timezone)).isoformat()

    def _save_media(self, media: dict) -> str | None:
        """Save media to disk and return the file path."""
        try:
            RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
            ext = media.get("mimetype", "image/jpeg").split("/")[-1]
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = RECEIPTS_DIR / filename
            filepath.write_bytes(base64.b64decode(media["data"]))
            logger.info(f"Saved media: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Error saving media: {e}")
            return None

    async def handle_incoming(self, text: str, media: dict | None, source: str, reply_to: str | None = None):
        # 1. Mark as read + start typing (WhatsApp only)
        if source == "whatsapp" and reply_to:
            await self.whatsapp.mark_read(reply_to)
            await self.whatsapp.send_typing(reply_to)

        # 2. Save media to disk
        media_path = None
        if media and media.get("data"):
            media_path = self._save_media(media)

        # 3. Save user message
        user_msg = await self.mensaje_repo.save({
            "role": "user",
            "content": text,
            "media_path": media_path,
            "source": source,
            "timestamp": self._now_iso(),
        })

        # 4. Process
        result = await self.processor.process(text=text, media=media)

        # 5. Stop typing
        if source == "whatsapp" and reply_to:
            await self.whatsapp.send_typing(reply_to, stop=True)

        # 6. Append model indicator
        response_text = result.response_text
        if result.model:
            response_text += f"\n_via {result.model}_"

        # 7. Save bot response
        bot_msg = await self.mensaje_repo.save({
            "role": "bot",
            "content": response_text,
            "source": "bot",
            "timestamp": self._now_iso(),
            "gastoIds": result.gasto_ids or [],
            "model": result.model,
        })

        # 8. Reply via WhatsApp
        if source == "whatsapp" and reply_to:
            await self.whatsapp.send_message(to=reply_to, message=response_text)

        # 9. Broadcast to web clients
        await self.ws_manager.broadcast({
            "type": "new_messages",
            "user_message": user_msg,
            "bot_response": bot_msg,
        })

        return result

    async def send_proactive(self, message: str):
        bot_msg = await self.mensaje_repo.save({
            "role": "bot",
            "content": message,
            "source": "bot_proactive",
            "timestamp": self._now_iso(),
        })

        await self.whatsapp.send_message(
            to=self.whatsapp.my_number,
            message=message,
        )

        await self.ws_manager.broadcast({
            "type": "new_messages",
            "bot_response": bot_msg,
        })
