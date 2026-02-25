import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    response_text: str
    gasto_ids: list[str] = field(default_factory=list)


class Processor:
    def __init__(self, text_parser, receipt_parser, gasto_repo,
                 ingreso_repo, budget_service, deuda_repo):
        self.text_parser = text_parser
        self.receipt_parser = receipt_parser
        self.gasto_repo = gasto_repo
        self.ingreso_repo = ingreso_repo
        self.budget = budget_service
        self.deuda_repo = deuda_repo

    async def process(self, text: str, media: dict | None = None) -> ProcessResult:

        # --- RECEIPT PHOTO ---
        if media and media.get("mimetype", "").startswith("image/"):
            items = await self.receipt_parser.parse(
                image_b64=media["data"],
                mime_type=media["mimetype"],
            )
            gasto_ids = []
            lines = []
            total = 0

            for item in items.get("items", []):
                gasto_id = await self.gasto_repo.create(
                    monto=item["monto"],
                    categoria=item["categoria"],
                    descripcion=item["descripcion"],
                    fuente="recibo",
                )
                gasto_ids.append(gasto_id)
                lines.append(f"  | {item['categoria'].title()} S/{item['monto']:.2f} ({item['descripcion']})")
                total += item["monto"]

            establecimiento = items.get("establecimiento", "Recibo")
            response = f"Registre {len(items.get('items', []))} items de {establecimiento}:\n"
            response += "\n".join(lines)
            response += f"\n  Total: S/{total:.2f}"

            alertas = await self.budget.check_alerts_batch(items.get("items", []))
            if alertas:
                response += "\n\n" + "\n".join(alertas)

            return ProcessResult(response_text=response, gasto_ids=gasto_ids)

        # --- TEXT ---
        if not text.strip():
            return ProcessResult(response_text="Envía un mensaje de texto o una foto de recibo.")

        parsed = await self.text_parser.parse(text)
        tipo = parsed.get("tipo", "desconocido")

        if tipo == "gasto":
            gasto_id = await self.gasto_repo.create(
                monto=parsed["monto"],
                categoria=parsed["categoria"],
                descripcion=parsed["descripcion"],
                fuente="texto",
            )
            response = f"{parsed['categoria'].title()} S/{parsed['monto']:.2f} ({parsed['descripcion']})"

            alerta = await self.budget.check_alert(parsed["categoria"])
            if alerta:
                response += f"\n\n{alerta}"

            return ProcessResult(response_text=response, gasto_ids=[gasto_id])

        elif tipo == "ingreso":
            await self.ingreso_repo.create(
                monto=parsed["monto"],
                fuente=parsed["descripcion"],
            )
            return ProcessResult(
                response_text=f"Ingreso: S/{parsed['monto']:.2f} ({parsed['descripcion']})"
            )

        elif tipo == "consulta":
            return await self._handle_query(text)

        elif tipo == "comando":
            return await self._handle_command(text, parsed)

        return ProcessResult(
            response_text="No entendi. Intenta: 'almuerzo 18' o 'cuanto llevo hoy'"
        )

    async def _handle_query(self, text: str) -> ProcessResult:
        text_lower = text.lower()
        if any(w in text_lower for w in ["hoy", "dia", "día"]):
            return ProcessResult(response_text=await self.gasto_repo.resumen_hoy())
        if any(w in text_lower for w in ["semana", "semanal"]):
            return ProcessResult(response_text=await self.gasto_repo.resumen_semana())
        if any(w in text_lower for w in ["mes", "mensual"]):
            return ProcessResult(response_text=await self.gasto_repo.resumen_mes())
        if any(w in text_lower for w in ["deuda", "deudas"]):
            return ProcessResult(response_text=await self.deuda_repo.resumen())
        return ProcessResult(
            response_text="Prueba: 'cuanto llevo hoy', 'resumen semana', 'mis deudas'"
        )

    async def _handle_command(self, text: str, parsed: dict) -> ProcessResult:
        return ProcessResult(response_text="Comando recibido, en construccion")
