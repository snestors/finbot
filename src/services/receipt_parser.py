import base64
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

RECEIPT_PROMPT = """Analiza este recibo/boleta. Responde SOLO JSON válido, sin markdown, sin ```json:
{
  "establecimiento": "nombre",
  "fecha": "YYYY-MM-DD o null",
  "items": [{"descripcion": "str", "cantidad": 1, "monto": 25.00,
             "categoria": "comida|bebidas|delivery|transporte|servicios|salud|compras|otros"}],
  "total": 33.00,
  "moneda": "PEN"
}"""


class ReceiptParser:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def parse(self, image_b64: str, mime_type: str) -> dict:
        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Content(role="user", parts=[
                        types.Part.from_bytes(
                            data=base64.b64decode(image_b64),
                            mime_type=mime_type,
                        ),
                        types.Part.from_text(RECEIPT_PROMPT),
                    ])
                ],
            )
            raw = response.text.strip().strip("```json").strip("```").strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error parsing receipt: {e}")
            return {"establecimiento": "Desconocido", "items": [], "total": 0, "moneda": "PEN"}
