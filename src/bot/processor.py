"""Processor — thin orchestrator for the message processing pipeline.

Processing flow:
  1. Media handling (receipts, documents) — bypasses text pipeline
  2. Fast path (regex, zero LLM calls) — handles ~85% of text messages
  3a. Unified agent (Claude tool_use) — when UNIFIED_AGENT_ENABLED=True
  3b. Legacy pipeline (router -> specialized agents) — when UNIFIED_AGENT_ENABLED=False

When the unified agent is enabled, the router and specialized agents (finance,
analysis, admin, chat) are bypassed entirely. The legacy pipeline remains as
a fallback if the unified agent encounters an error.
"""
import logging
import time
from dataclasses import dataclass, field

from src.agents.fast_path import try_fast_path
from src.config import settings

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
                 budget_service=None, mensaje_repo=None,
                 unified_agent=None):
        self.router = router
        self.registry = registry
        self.executor = executor
        self.repos = repos
        self.receipt_parser = receipt_parser
        self.document_parser = document_parser
        self.budget = budget_service
        self.mensaje_repo = mensaje_repo
        self.unified_agent = unified_agent  # Phase 2: UnifiedAgent (tool_use)
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

        # 0. Fast path — regex-based extraction, zero LLM calls
        if settings.fast_path_enabled:
            fp_result = await self._try_fast_path(text)
            if fp_result is not None:
                return fp_result

        # 1. Get conversation history for context
        history = await self._get_history()

        # 2. Unified agent path — single agent handles all domains via tool_use
        #    When enabled: fast_path -> unified_agent (no router needed)
        if settings.unified_agent_enabled and self.unified_agent:
            return await self._try_unified_agent(text, history)

        # 3. Legacy pipeline — router -> specialized agents (finance/analysis/admin/chat)
        #    DEPRECATED: This path is active only when UNIFIED_AGENT_ENABLED=False.
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

        gasto_ids = []

        MAX_TOOL_LOOPS = 12
        scratchpad = Scratchpad()
        did_mutate = False
        system_errors = []
        system_confirms = []

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

                # Track real action status
                if "ok" in action_result:
                    if not action_result["ok"]:
                        system_errors.append(action_result.get("message", "Error desconocido"))
                    else:
                        msg = action_result.get("message", "")
                        if msg:
                            system_confirms.append(msg)

                # Track in scratchpad
                action_label = f"tool:{accion.get('name', '?')}" if tipo == "tool" else tipo
                result_text = action_result.get("data_response", "") or action_result.get("message", "") or action_result.get("alert", "") or "OK"
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
                if system_errors:
                    response += "\n⚠️ " + " | ".join(system_errors)
                elif system_confirms:
                    response += "\n✅ " + " | ".join(system_confirms)
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

    async def _try_fast_path(self, text: str) -> ProcessResult | None:
        """Attempt regex-based fast path. Returns ProcessResult or None."""
        t0 = time.monotonic()
        fp = try_fast_path(text)
        if fp is None:
            return None

        actions, response_text = fp
        elapsed_ms = (time.monotonic() - t0) * 1000

        await self._emit("fast_path", f"Fast path ({elapsed_ms:.0f}ms)")
        logger.info(f"[fast_path] Matched in {elapsed_ms:.1f}ms: '{text[:50]}'")

        # Execute actions through the normal ActionExecutor
        gasto_ids = []
        system_errors = []
        system_confirms = []

        for accion in actions:
            tipo = accion.get("tipo", "?")
            await self._emit("action", f"Ejecutando: {tipo}")

            action_result = await self.executor.execute(accion)

            if action_result.get("gasto_id"):
                gasto_ids.append(action_result["gasto_id"])
            if action_result.get("movimiento_id"):
                gasto_ids.append(action_result["movimiento_id"])

            if "ok" in action_result:
                if not action_result["ok"]:
                    system_errors.append(action_result.get("message", "Error desconocido"))
                else:
                    msg = action_result.get("message", "")
                    if msg:
                        system_confirms.append(msg)

            if action_result.get("data_response"):
                response_text += "\n\n" + action_result["data_response"]
            if action_result.get("alert"):
                response_text += "\n" + action_result["alert"]

        if system_errors:
            response_text += "\n\u26a0\ufe0f " + " | ".join(system_errors)
        elif system_confirms:
            response_text += "\n\u2705 " + " | ".join(system_confirms)

        await self._emit("done", "")
        return ProcessResult(
            response_text=response_text,
            gasto_ids=gasto_ids,
            model="fast_path",
        )

    async def _try_unified_agent(self, text: str, history: list[dict]) -> ProcessResult:
        """Route through the unified agent (Claude tool_use). Phase 2."""
        await self._emit("unified", "Procesando...")
        logger.info(f"[unified] Processing: '{text[:50]}'")

        try:
            result = await self.unified_agent.process(
                text=text,
                history=history,
                repos=self.repos,
                executor=self.executor,
                emit_fn=self._emit,
            )

            await self._emit("done", "")
            return ProcessResult(
                response_text=result.get("response_text", ""),
                gasto_ids=result.get("gasto_ids", []),
                model=result.get("model", ""),
            )

        except Exception as e:
            logger.error(f"[unified] Error: {e}", exc_info=True)
            await self._emit("done", "")
            # Fall through to old pipeline on error
            logger.info("[unified] Falling back to old agent pipeline")
            return await self._process_with_old_pipeline(text, history)

    async def _process_with_old_pipeline(self, text: str, history: list[dict]) -> ProcessResult:
        """Old agent pipeline (router + specialized agents). Used as fallback."""
        await self._emit("routing", "Analizando mensaje...")
        route = await self.router.route(text, history)
        agent = self.registry.get(route)

        if not agent:
            logger.error(f"No agent found for route '{route}', falling back to chat")
            agent = self.registry.get("chat")

        logger.info(f"Routed '{text[:50]}' -> {agent.AGENT_NAME}")
        await self._emit("routed", f"Agente: {agent.AGENT_NAME}")

        context = await agent.build_context(repos=self.repos)
        await self._emit("thinking", "Pensando...")
        result = await agent.parse(text, context=context, history=history)

        response = result.get("respuesta", "")
        acciones = result.get("acciones", [])
        model = result.get("_model", "")
        gasto_ids = []

        for accion in acciones:
            action_result = await self.executor.execute(accion)
            if action_result.get("gasto_id"):
                gasto_ids.append(action_result["gasto_id"])
            if action_result.get("movimiento_id"):
                gasto_ids.append(action_result["movimiento_id"])
            if action_result.get("data_response"):
                response += "\n\n" + action_result["data_response"]
            if action_result.get("alert"):
                response += "\n" + action_result["alert"]

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
