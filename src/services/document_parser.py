import base64
import json
import logging
import tempfile
from pathlib import Path

import fitz  # pymupdf
import openpyxl
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DOCUMENT_PROMPT = """Analiza este documento financiero. Puede ser un estado de cuenta, factura, recibo, reporte, etc.
Extrae TODA la información financiera relevante.
Responde SOLO JSON válido, sin markdown, sin ```:
{
  "tipo_documento": "factura|estado_cuenta|recibo|reporte|otro",
  "emisor": "nombre de la empresa/banco",
  "fecha": "YYYY-MM-DD o null",
  "resumen": "resumen breve del documento",
  "items": [{"descripcion": "str", "monto": 25.00, "categoria": "comida|transporte|servicios|salud|compras|otros"}],
  "total": 33.00,
  "moneda": "PEN"
}
Si no hay items individuales, pon el total como un solo item."""


class DocumentParser:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        text_parts = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n".join(text_parts)

    def _extract_excel_text(self, excel_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=True) as tmp:
            tmp.write(excel_bytes)
            tmp.flush()
            wb = openpyxl.load_workbook(tmp.name, read_only=True)
            lines = []
            for sheet in wb.worksheets:
                lines.append(f"--- Hoja: {sheet.title} ---")
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c) if c is not None else "" for c in row]
                    lines.append(" | ".join(cells))
            wb.close()
            return "\n".join(lines)

    async def parse(self, file_b64: str, mime_type: str) -> dict:
        try:
            file_bytes = base64.b64decode(file_b64)

            if "pdf" in mime_type:
                text = self._extract_pdf_text(file_bytes)
                return await self._analyze_text(text)
            elif "spreadsheet" in mime_type or "excel" in mime_type or "xlsx" in mime_type:
                text = self._extract_excel_text(file_bytes)
                return await self._analyze_text(text)
            elif mime_type.startswith("image/"):
                return await self._analyze_image(file_b64, mime_type)
            else:
                return {"tipo_documento": "otro", "resumen": "Formato no soportado", "items": [], "total": 0, "moneda": "PEN"}
        except Exception as e:
            logger.error(f"Error parsing document: {e}")
            return {"tipo_documento": "error", "resumen": str(e), "items": [], "total": 0, "moneda": "PEN"}

    async def _analyze_text(self, text: str) -> dict:
        prompt = f"{DOCUMENT_PROMPT}\n\nContenido del documento:\n{text[:8000]}"
        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(raw)

    async def _analyze_image(self, image_b64: str, mime_type: str) -> dict:
        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type=mime_type),
                    types.Part.from_text(DOCUMENT_PROMPT),
                ])
            ],
        )
        raw = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
