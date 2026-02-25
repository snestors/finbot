import json
import logging
from google import genai

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un parser financiero. Extrae datos de una transacción.
Responde SOLO JSON válido, sin markdown, sin ```json.

{"tipo": "gasto|ingreso|consulta|comando", "monto": number, "categoria": "string", "descripcion": "string"}

Categorías gasto: comida, transporte, delivery, entretenimiento, servicios, salud, deuda_pago, compras, otros
Ingreso: categoria = "ingreso"
Pregunta (cuánto llevo, resumen, cuánto gasté): tipo = "consulta", monto = 0
Comando (presupuesto, agregar deuda, borrar, eliminar): tipo = "comando", monto = 0

Ejemplos:
- "almuerzo 18" → {"tipo":"gasto","monto":18,"categoria":"comida","descripcion":"almuerzo"}
- "taxi 8.50" → {"tipo":"gasto","monto":8.5,"categoria":"transporte","descripcion":"taxi"}
- "rappi 35" → {"tipo":"gasto","monto":35,"categoria":"delivery","descripcion":"rappi"}
- "me pagaron 3500 sueldo" → {"tipo":"ingreso","monto":3500,"categoria":"ingreso","descripcion":"sueldo"}
- "cuánto llevo hoy" → {"tipo":"consulta","monto":0,"categoria":"","descripcion":"resumen hoy"}
- "resumen semana" → {"tipo":"consulta","monto":0,"categoria":"","descripcion":"resumen semana"}
- "presupuesto delivery 200" → {"tipo":"comando","monto":200,"categoria":"delivery","descripcion":"set presupuesto"}"""


class TextParser:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def parse(self, text: str) -> dict:
        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=f'{SYSTEM_PROMPT}\n\nMensaje: "{text}"',
            )
            raw = response.text.strip().strip("```json").strip("```").strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error parsing text '{text}': {e}")
            return {"tipo": "desconocido", "monto": 0, "categoria": "", "descripcion": text}
