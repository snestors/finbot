import logging
import httpx
from src.config import settings

logger = logging.getLogger(__name__)


class WhatsAppChannel:
    def __init__(self):
        self.base_url = settings.bridge_url
        self.my_number = settings.whatsapp_my_number
        self._client = httpx.AsyncClient(timeout=30)

    async def send_message(self, to: str, message: str):
        try:
            resp = await self._client.post(
                f"{self.base_url}/send",
                json={"to": to, "message": message},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Error sending WhatsApp message: {e}")

    async def mark_read(self, chat_id: str):
        try:
            await self._client.post(
                f"{self.base_url}/mark-read",
                json={"chatId": chat_id},
            )
        except Exception:
            pass

    async def send_typing(self, chat_id: str, stop: bool = False):
        try:
            await self._client.post(
                f"{self.base_url}/typing",
                json={"chatId": chat_id, "state": "stop" if stop else "typing"},
            )
        except Exception:
            pass

    async def get_status(self) -> dict:
        try:
            resp = await self._client.get(f"{self.base_url}/status")
            return resp.json()
        except httpx.HTTPError:
            return {"ready": False, "error": "Bridge not reachable"}

    async def get_qr(self) -> str | None:
        try:
            resp = await self._client.get(f"{self.base_url}/qr")
            return resp.json().get("qr")
        except httpx.HTTPError:
            return None

    async def close(self):
        await self._client.aclose()
