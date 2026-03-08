"""Unified Agent — single agent using Claude's native tool_use API.

Replaces the 4 specialized agents (finance, analysis, admin, chat) with one
agent that lets Claude decide which tools to call. The ActionExecutor is
reused as-is — tool calls map 1:1 to executor actions via tool_schemas.
"""
import logging
from datetime import date
from pathlib import Path

from src.agents.context_builders import (
    build_finance_context,
    build_energy_context,
    build_printer_context,
)
from src.agents.tool_schemas import TOOLS, tool_call_to_action
from src.llm import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
AGENTS_DIR = PROJECT_ROOT / "data" / "agents"
ALMA_PATH = PROJECT_ROOT / "data" / "alma.md"
SHARED_PATH = AGENTS_DIR / "_shared.md"
UNIFIED_PROMPT_PATH = AGENTS_DIR / "unified.md"

# Max tool-use round trips before forcing a final response
MAX_TOOL_ROUNDS = 8

# Action types that mutate data (need context refresh)
_MUTATING_ACTIONS = {
    "movimiento", "gasto", "ingreso", "pago_tarjeta", "transferencia",
    "pago_deuda", "pago_cobro", "eliminar_movimiento", "actualizar_movimiento",
    "eliminar_movimientos", "importar_estado_cuenta",
    "crear_cuenta", "actualizar_cuenta", "tarjeta", "agregar_deuda", "cobro",
    "set_presupuesto", "set_perfil",
}


class UnifiedAgent:
    """Single agent that handles all domains via Claude tool_use."""

    AGENT_NAME = "unified"
    PROMPT_FILE = "unified.md"

    def __init__(self, llm_client: LLMClient, engram_client=None):
        self.llm = llm_client
        self.engram = engram_client
        self._prompt_cache: str | None = None
        self._prompt_mtime: float = 0.0
        self._alma_cache: str | None = None
        self._shared_cache: str | None = None

    # ------------------------------------------------------------------
    # Prompt loading (hot-reload, same pattern as BaseAgent)
    # ------------------------------------------------------------------

    def _load_alma(self) -> str:
        if self._alma_cache is None:
            try:
                self._alma_cache = ALMA_PATH.read_text(encoding="utf-8")
            except Exception:
                self._alma_cache = ""
        return self._alma_cache

    def _load_shared(self) -> str:
        if self._shared_cache is None:
            try:
                self._shared_cache = SHARED_PATH.read_text(encoding="utf-8")
            except Exception:
                self._shared_cache = ""
        return self._shared_cache

    def _load_prompt(self) -> str:
        try:
            mtime = UNIFIED_PROMPT_PATH.stat().st_mtime
            if self._prompt_cache is None or mtime > self._prompt_mtime:
                self._prompt_cache = UNIFIED_PROMPT_PATH.read_text(encoding="utf-8")
                self._prompt_mtime = mtime
                logger.info("[unified] Prompt reloaded")
        except Exception as e:
            logger.warning(f"[unified] Failed to load prompt: {e}")
            if self._prompt_cache is None:
                self._prompt_cache = ""
        return self._prompt_cache

    def _build_system_prompt(self, context: str = "") -> str:
        """Assemble full system prompt: alma + agent prompt + context."""
        # Shared rules have JSON format instructions that don't apply to tool_use.
        # We include alma and the unified prompt only.
        parts = [self._load_alma(), self._load_prompt()]
        prompt = "\n\n".join(p for p in parts if p)
        prompt = prompt.replace("{fecha_hoy}", date.today().isoformat())
        if context:
            prompt += f"\n\n## CONTEXTO ACTUAL\n{context}"
        return prompt

    # ------------------------------------------------------------------
    # Context building (combines all domain contexts)
    # ------------------------------------------------------------------

    async def build_context(self, repos: dict, user_message: str = "") -> str:
        """Build unified context covering all domains."""
        parts = []

        # Finance context (accounts, today's movements, cards, debts, cobros)
        try:
            finance = await build_finance_context(repos)
            if finance:
                parts.append(finance)
        except Exception as e:
            logger.warning(f"[unified] finance context error: {e}")

        # Analysis context additions (budgets, summaries) — only parts not in finance
        try:
            presupuesto_repo = repos.get("presupuesto")
            mov_repo = repos.get("movimiento")
            if presupuesto_repo and mov_repo:
                presupuestos = await presupuesto_repo.get_all()
                if presupuestos:
                    budget_lines = []
                    for p in presupuestos:
                        total = await mov_repo.total_categoria_mes(p["categoria"])
                        pct = (total / p["limite_mensual"] * 100) if p["limite_mensual"] > 0 else 0
                        budget_lines.append(f"  {p['categoria']}: S/{total:.0f}/S/{p['limite_mensual']:.0f} ({pct:.0f}%)")
                    parts.append("Presupuestos:\n" + "\n".join(budget_lines))
        except Exception as e:
            logger.warning(f"[unified] budget context error: {e}")

        # Energy context
        try:
            energy = await build_energy_context(repos)
            if energy:
                parts.append("Energia:\n" + energy)
        except Exception:
            pass

        # 3D Printer context
        try:
            printer = build_printer_context(repos)
            if printer:
                parts.append("Impresora 3D:\n" + printer)
        except Exception:
            pass

        # Memory context — engram (semantic) > legacy MemoriaRepo (fallback)
        mem_added = False
        if self.engram:
            try:
                # Semantic search based on user message gives the most relevant memories
                mem_context = await self.engram.format_for_context(
                    query=user_message, limit=5,
                )
                if mem_context:
                    parts.append(mem_context)
                    mem_added = True
            except Exception as e:
                logger.warning(f"[unified] engram context error: {e}")

        # Fallback to legacy MemoriaRepo if engram didn't provide memories
        if not mem_added:
            memoria_repo = repos.get("memoria")
            if memoria_repo:
                try:
                    mem_context = await memoria_repo.format_for_context()
                    if mem_context:
                        parts.append(mem_context)
                except Exception:
                    pass

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process(
        self,
        text: str,
        history: list[dict],
        repos: dict,
        executor,
        emit_fn=None,
    ) -> dict:
        """Process a user message through Claude tool_use.

        Returns:
            {"response_text": str, "gasto_ids": list, "model": str}
        """
        # Build context and system prompt (pass user text for semantic memory recall)
        context = await self.build_context(repos, user_message=text)
        system = self._build_system_prompt(context)

        # Build initial messages
        messages = self._build_messages(text, history)

        gasto_ids = []
        model = ""

        for round_i in range(MAX_TOOL_ROUNDS):
            if emit_fn:
                if round_i == 0:
                    await emit_fn("thinking", "Pensando...")
                else:
                    await emit_fn("thinking", f"Procesando (paso {round_i + 1})...")

            # Call Claude with tools
            try:
                llm_response = await self.llm.generate_with_tools(
                    system=system,
                    messages=messages,
                    tools=TOOLS,
                )
            except Exception as e:
                logger.error(f"[unified] LLM error: {e}")
                return {
                    "response_text": "Perdon, tuve un problema procesando eso. Intenta de nuevo.",
                    "gasto_ids": [],
                    "model": "",
                }

            model = llm_response.model

            # If no tool calls, we're done — return the text response
            if not llm_response.tool_calls:
                return {
                    "response_text": llm_response.text,
                    "gasto_ids": gasto_ids,
                    "model": model,
                }

            # Claude wants to call tools — execute them
            # First, append the assistant message (with text + tool_use blocks)
            assistant_content = self._build_assistant_content(llm_response)
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool call and collect results
            tool_results = []
            did_mutate = False

            for tc in llm_response.tool_calls:
                tool_name = tc["name"]
                tool_input = tc["input"]
                tool_use_id = tc["id"]

                if emit_fn:
                    await emit_fn("tool", f"Ejecutando: {tool_name}")

                # Convert to ActionExecutor action and execute
                action = tool_call_to_action(tool_name, tool_input)
                logger.info(f"[unified] Tool call: {tool_name} -> action tipo={action.get('tipo')}")

                try:
                    result = await executor.execute(action)
                except Exception as e:
                    logger.error(f"[unified] Executor error for {tool_name}: {e}")
                    result = {"ok": False, "message": f"Error: {e}"}

                # Track gasto/movimiento IDs
                if result.get("gasto_id"):
                    gasto_ids.append(result["gasto_id"])
                if result.get("movimiento_id"):
                    gasto_ids.append(result["movimiento_id"])

                # Track mutations
                if action.get("tipo") in _MUTATING_ACTIONS:
                    did_mutate = True

                # Build tool result content for Claude
                result_text = self._format_tool_result(result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_text,
                })

            # Append tool results as a user message
            messages.append({"role": "user", "content": tool_results})

            # Refresh context if data changed (no semantic search on refresh)
            if did_mutate:
                context = await self.build_context(repos, user_message="")
                system = self._build_system_prompt(context)

            # On the last allowed round, tell Claude to wrap up
            if round_i == MAX_TOOL_ROUNDS - 2:
                messages[-1]["content"].append({
                    "type": "text",
                    "text": "SISTEMA: Este es tu ultimo paso. Resume lo que hiciste y responde al usuario.",
                })

        # Loop exhausted — return whatever text we have
        logger.warning(f"[unified] Exhausted {MAX_TOOL_ROUNDS} rounds")
        return {
            "response_text": llm_response.text or "Listo, ejecute las acciones solicitadas.",
            "gasto_ids": gasto_ids,
            "model": model,
        }

    # ------------------------------------------------------------------
    # Message building
    # ------------------------------------------------------------------

    def _build_messages(self, user_message: str, history: list[dict]) -> list[dict]:
        """Build the initial messages array from conversation history.

        For tool_use, messages must be plain text (not tool_use/tool_result
        blocks from previous conversations). We flatten history to text.
        """
        messages = []
        if history:
            for msg in history[-20:]:
                role = "user" if msg.get("role") == "user" else "assistant"
                content = msg.get("content", "")
                if not content:
                    continue
                if role == "assistant" and len(content) > 1500:
                    content = content[:1000] + "\n...(truncado)...\n" + content[-500:]
                # Merge consecutive same-role messages
                if messages and messages[-1]["role"] == role:
                    messages[-1]["content"] += "\n" + content
                else:
                    messages.append({"role": role, "content": content})

        # Ensure first message is from user (Claude requirement)
        if messages and messages[0]["role"] == "assistant":
            messages.insert(0, {"role": "user", "content": "(inicio de conversacion)"})

        messages.append({"role": "user", "content": user_message})

        # Merge if last two are both user
        if len(messages) >= 2 and messages[-2]["role"] == "user":
            messages[-2]["content"] += "\n" + messages[-1]["content"]
            messages.pop()

        return messages

    def _build_assistant_content(self, llm_response: LLMResponse) -> list[dict]:
        """Build assistant message content blocks from LLM response.

        Claude tool_use requires the assistant message to contain the exact
        tool_use blocks it returned, so we rebuild them here.
        """
        content = []
        if llm_response.text:
            content.append({"type": "text", "text": llm_response.text})
        for tc in llm_response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })
        return content

    def _format_tool_result(self, result: dict) -> str:
        """Format an ActionExecutor result into a string for Claude."""
        parts = []

        if "data_response" in result and result["data_response"]:
            parts.append(str(result["data_response"]))
        elif "message" in result and result["message"]:
            ok = result.get("ok", True)
            prefix = "" if ok else "ERROR: "
            parts.append(f"{prefix}{result['message']}")

        if result.get("alert"):
            parts.append(f"ALERTA: {result['alert']}")

        if result.get("movimiento_id"):
            parts.append(f"(movimiento_id: {result['movimiento_id']})")

        if not parts:
            if result.get("ok"):
                return "OK"
            return "Ejecutado sin resultado."

        return "\n".join(parts)
