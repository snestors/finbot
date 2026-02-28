"""Processor — thin orchestrator that routes messages to specialized agents."""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    response_text: str
    gasto_ids: list[str] = field(default_factory=list)
    model: str = ""
    has_pending_actions: bool = False


@dataclass
class ScratchpadEntry:
    iteration: int
    action: str
    result: str


class Scratchpad:
    def __init__(self):
        self.entries: list[ScratchpadEntry] = []

    def add(self, iteration: int, action: str, result: str):
        if len(result) > 500:
            result = result[:300] + "\n...\n" + result[-200:]
        self.entries.append(ScratchpadEntry(iteration, action, result))

    def render(self) -> str:
        if not self.entries:
            return ""
        lines = ["## SCRATCHPAD (lo que ya hiciste)"]
        for e in self.entries:
            lines.append(f"[Paso {e.iteration}] {e.action}: {e.result}")
        return "\n".join(lines)


# Action types that modify data → trigger context refresh
_MUTATING_ACTIONS = {
    "movimiento", "gasto", "ingreso", "pago_tarjeta", "transferencia",
    "pago_deuda", "pago_cobro", "eliminar_movimiento", "actualizar_movimiento",
    "importar_estado_cuenta",
}


class Processor:
    def __init__(self, router, registry, executor, repos: dict,
                 receipt_parser=None, document_parser=None,
                 budget_service=None, mensaje_repo=None):
        self.router = router
        self.registry = registry
        self.executor = executor
        self.repos = repos
        self.receipt_parser = receipt_parser
        self.document_parser = document_parser
        self.budget = budget_service
        self.mensaje_repo = mensaje_repo
        self._message_bus = None  # Set by message_bus after init

    async def _emit(self, step: str, detail: str = ""):
        """Emit activity to web clients if message_bus is available."""
        if self._message_bus:
            try:
                await self._message_bus.emit_activity(step, detail)
            except Exception:
                pass

    async def process(self, text: str, media: dict | None = None) -> ProcessResult:
        # --- MEDIA ---
        if media and media.get("mimetype"):
            mime = media["mimetype"]
            if "pdf" in mime or "spreadsheet" in mime or "excel" in mime:
                await self._emit("media", "Procesando documento...")
                return await self._handle_document(media)
        if media and media.get("mimetype", "").startswith("image/"):
            await self._emit("media", "Analizando imagen...")
            return await self._handle_receipt(media)

        # --- TEXT ---
        if not text.strip():
            return ProcessResult(response_text="Envia un mensaje de texto o una foto de recibo.")

        # 1. Get history
        history = await self._get_history()

        # 2. Route to agent (async — may call LLM for ambiguous messages)
        await self._emit("routing", "Analizando mensaje...")
        route = await self.router.route(text, history)
        agent = self.registry.get(route)

        if not agent:
            logger.error(f"No agent found for route '{route}', falling back to chat")
            agent = self.registry.get("chat")

        logger.info(f"Routed '{text[:50]}' → {agent.AGENT_NAME}")
        await self._emit("routed", f"Agente: {agent.AGENT_NAME}")

        # 3. Build agent-specific context
        context = await agent.build_context(repos=self.repos)

        # 4. Parse with agent
        await self._emit("thinking", "Pensando...")
        result = await agent.parse(text, context=context, history=history)

        # 5. Execute actions (with agentic loop for tool-using agents)
        response = result.get("respuesta", "")
        acciones = result.get("acciones", [])
        model = result.get("_model", "")

        # Guard: if response claims an action was done but acciones is empty, warn
        if not acciones and model == "gemini":
            import re as _re
            _claim_patterns = _re.compile(
                r'(?:recordatorio|gasto|ingreso|presupuesto|deuda|cobro|cuenta|tarjeta|memoria|calendario|evento)'
                r'\s*#?\d*\s*(?:cread[oa]|eliminad[oa]|actualizad[oa]|registrad[oa]|guardad[oa]|importad[oa]|sincronizad[oa])',
                _re.IGNORECASE,
            )
            if _claim_patterns.search(response):
                logger.warning(f"[processor] Gemini claimed action but acciones=[], stripping claim")
                response += "\n\n⚠️ _No se ejecutó ninguna acción. Si esperabas un cambio, repite tu pedido._"
        gasto_ids = []

        MAX_TOOL_LOOPS = 12
        scratchpad = Scratchpad()
        did_mutate = False

        for loop_i in range(MAX_TOOL_LOOPS):
            tool_outputs = []

            for accion in acciones:
                tipo = accion.get("tipo", "?")
                if tipo == "tool":
                    tool_name = accion.get("name", "?")
                    await self._emit("tool", f"Ejecutando: {tool_name}")
                else:
                    await self._emit("action", f"Ejecutando: {tipo}")
                action_result = await self.executor.execute(accion)
                if action_result.get("gasto_id"):
                    gasto_ids.append(action_result["gasto_id"])
                if action_result.get("movimiento_id"):
                    gasto_ids.append(action_result["movimiento_id"])

                # Track in scratchpad
                action_label = f"tool:{accion.get('name', '?')}" if tipo == "tool" else tipo
                result_text = action_result.get("data_response", "") or action_result.get("alert", "") or "OK"
                scratchpad.add(loop_i, action_label, result_text)

                # Track mutations for context refresh
                if tipo in _MUTATING_ACTIONS:
                    did_mutate = True

                if action_result.get("data_response"):
                    tool_outputs.append(action_result["data_response"])
                if action_result.get("alert"):
                    tool_outputs.append(action_result["alert"])

            # If no tool actions or no outputs to feed back, we're done
            has_tools = any(a.get("tipo") == "tool" for a in acciones)
            if not has_tools or not tool_outputs:
                # Append any data_response/alert to final response
                if tool_outputs:
                    response += "\n\n" + "\n\n".join(tool_outputs)
                break

            # Refresh context if data changed
            if did_mutate:
                context = await agent.build_context(repos=self.repos)
                did_mutate = False

            # Feed tool results back to the LLM for next step
            logger.info(f"[agentic-loop] iteration {loop_i + 1}, {len(tool_outputs)} tool outputs")
            await self._emit("thinking", f"Analizando resultados (paso {loop_i + 1})...")
            followup = "RESULTADOS DE HERRAMIENTAS:\n---\n" + "\n---\n".join(tool_outputs)
            followup += "\n\n" + scratchpad.render()
            # On last iteration, tell the agent to wrap up
            if loop_i == MAX_TOOL_LOOPS - 2:
                followup += "\n\nIMPORTANTE: Este es tu ultimo paso. Resume lo que hiciste y responde al usuario."
            result = await agent.parse(followup, context=context, history=history)
            response = result.get("respuesta", response)
            acciones = result.get("acciones", [])
            if not acciones:
                break  # Agent is done
        else:
            # Loop exhausted — execute any remaining actions and summarize
            if acciones:
                logger.warning(f"[agentic-loop] exhausted after {MAX_TOOL_LOOPS} iterations, executing final actions")
                for accion in acciones:
                    action_result = await self.executor.execute(accion)
                    if action_result.get("data_response"):
                        tool_outputs.append(action_result["data_response"])
                if tool_outputs:
                    response += "\n\n" + "\n\n".join(tool_outputs)

        await self._emit("done", "")
        return ProcessResult(response_text=response, gasto_ids=gasto_ids, model=model)

    async def _handle_receipt(self, media: dict) -> ProcessResult:
        if not self.receipt_parser:
            return ProcessResult(response_text="No puedo procesar recibos todavia.")
        items = await self.receipt_parser.parse(
            image_b64=media["data"],
            mime_type=media["mimetype"],
        )
        gasto_ids = []
        lines = []
        total = 0

        mov_repo = self.repos.get("movimiento")
        for item in items.get("items", []):
            if mov_repo:
                gasto_id = await mov_repo.create(
                    tipo="gasto",
                    monto=item["monto"],
                    categoria=item["categoria"],
                    descripcion=item["descripcion"],
                    fuente="recibo",
                )
            else:
                gasto_id = await self.repos["gasto"].create(
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

        if self.budget:
            alertas = await self.budget.check_alerts_batch(items.get("items", []))
            if alertas:
                response += "\n\n" + "\n".join(alertas)

        return ProcessResult(response_text=response, gasto_ids=gasto_ids)

    async def _handle_document(self, media: dict) -> ProcessResult:
        if not self.document_parser:
            return ProcessResult(response_text="No puedo procesar documentos todavia.")
        parsed = await self.document_parser.parse(
            file_b64=media["data"],
            mime_type=media["mimetype"],
        )
        gasto_ids = []
        lines = []
        total = 0
        mov_repo = self.repos.get("movimiento")
        for item in parsed.get("items", []):
            if mov_repo:
                gasto_id = await mov_repo.create(
                    tipo="gasto",
                    monto=item["monto"],
                    categoria=item.get("categoria", "otros"),
                    descripcion=item.get("descripcion", ""),
                    fuente="documento",
                )
            else:
                gasto_id = await self.repos["gasto"].create(
                    monto=item["monto"],
                    categoria=item.get("categoria", "otros"),
                    descripcion=item.get("descripcion", ""),
                    fuente="documento",
                )
            gasto_ids.append(gasto_id)
            cat = item.get("categoria", "otros").title()
            desc = item.get("descripcion", "")
            monto = item["monto"]
            lines.append(f"  | {cat} S/{monto:.2f} ({desc})")
            total += item["monto"]
        tipo = parsed.get("tipo_documento", "documento")
        emisor = parsed.get("emisor", "Documento")
        response = "Analice " + tipo + " de " + emisor + ":\n"
        if parsed.get("resumen"):
            response += parsed["resumen"] + "\n\n"
        if lines:
            response += "Registre:\n" + "\n".join(lines)
            response += "\n  Total: S/" + f"{total:.2f}"
        elif not parsed.get("items"):
            response += parsed.get("resumen", "No encontre items financieros.")
        if self.budget:
            alertas = await self.budget.check_alerts_batch(parsed.get("items", []))
            if alertas:
                response += "\n\n" + "\n".join(alertas)
        return ProcessResult(response_text=response, gasto_ids=gasto_ids)

    async def _get_history(self) -> list[dict]:
        if not self.mensaje_repo:
            return []
        try:
            return await self.mensaje_repo.get_history(limit=20)
        except Exception:
            return []
