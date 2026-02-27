"""Base agent class with hot-reloadable prompts and LLM integration."""
import json
import logging
import re
from pathlib import Path

from src.llm import LLMClient

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
AGENTS_DIR = PROJECT_ROOT / "data" / "agents"
ALMA_PATH = PROJECT_ROOT / "data" / "alma.md"


class BaseAgent:
    """Base class for all specialized agents. Subclasses set AGENT_NAME and PROMPT_FILE."""

    AGENT_NAME: str = "base"
    PROMPT_FILE: str = "base.md"

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self._prompt_cache: str | None = None
        self._prompt_mtime: float = 0.0
        self._alma_cache: str | None = None
        self._shared_cache: str | None = None

    def _load_alma(self) -> str:
        if self._alma_cache is None:
            try:
                self._alma_cache = ALMA_PATH.read_text(encoding="utf-8")
            except Exception:
                self._alma_cache = ""
        return self._alma_cache

    def _load_shared_rules(self) -> str:
        if self._shared_cache is None:
            try:
                self._shared_cache = (AGENTS_DIR / "_shared.md").read_text(encoding="utf-8")
            except Exception:
                self._shared_cache = ""
        return self._shared_cache

    def _load_prompt(self) -> str:
        """Load agent-specific prompt with hot-reload on file change."""
        prompt_path = AGENTS_DIR / self.PROMPT_FILE
        try:
            mtime = prompt_path.stat().st_mtime
            if self._prompt_cache is None or mtime > self._prompt_mtime:
                self._prompt_cache = prompt_path.read_text(encoding="utf-8")
                self._prompt_mtime = mtime
                logger.info(f"[{self.AGENT_NAME}] Prompt reloaded from {self.PROMPT_FILE}")
        except Exception as e:
            logger.warning(f"[{self.AGENT_NAME}] Failed to load prompt: {e}")
            if self._prompt_cache is None:
                self._prompt_cache = ""
        return self._prompt_cache

    def build_system_prompt(self) -> str:
        """Assemble full system prompt: alma + shared rules + agent-specific prompt."""
        parts = [self._load_alma(), self._load_shared_rules(), self._load_prompt()]
        return "\n\n".join(p for p in parts if p)

    async def build_context(self, **kwargs) -> str:
        """Override in subclasses to build agent-specific context."""
        return ""

    async def parse(self, text: str, context: str = "", history: list[dict] = None) -> dict:
        """Send message to LLM and extract JSON response. Retries once on failure."""
        system = self.build_system_prompt()
        if context:
            system += f"\n\n## CONTEXTO ACTUAL\n{context}"

        hist = self._prepare_history(history or [])

        last_error = None
        last_raw = ""
        last_model = ""
        for attempt in range(2):
            try:
                user_msg = text if attempt == 0 else (
                    f'{text}\n\nSISTEMA: Tu respuesta anterior no fue JSON valido. '
                    f'Responde SOLO con JSON puro: {{"respuesta": "...", "acciones": [...]}}'
                )
                llm_response = await self.llm.generate(
                    system=system,
                    user_message=user_msg,
                    history=hist,
                )
                raw = llm_response.text.strip()
                model = llm_response.model
                last_raw = raw
                last_model = model
                result = _extract_json(raw)

                if result and "respuesta" in result:
                    if "acciones" not in result:
                        result["acciones"] = []
                    result["_model"] = model
                    return result

                if result:
                    return {"respuesta": str(result), "acciones": [], "_model": model}

                last_error = f"Invalid JSON: {raw[:200]}"
                logger.warning(f"[{self.AGENT_NAME}] Parse attempt {attempt + 1} failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"[{self.AGENT_NAME}] Parse attempt {attempt + 1} error: {e}")

        # Both attempts failed — if we got plain text, use it as response
        # instead of showing a generic error message
        if last_raw and not last_raw.startswith('{'):
            logger.info(f"[{self.AGENT_NAME}] Using plain text fallback for '{text[:40]}'")
            return {"respuesta": last_raw, "acciones": [], "_model": last_model}

        logger.error(f"[{self.AGENT_NAME}] Failed after retries for '{text[:80]}': {last_error}")
        return {
            "respuesta": "Perdon, tuve un problema procesando eso. Intenta decirlo de otra forma.",
            "acciones": [],
        }

    def _prepare_history(self, history: list[dict]) -> list[dict]:
        """Prepare conversation history for LLM."""
        result = []
        for msg in history[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                result.append({"role": role, "content": content})
        return result


def _extract_json(raw: str) -> dict | None:
    """Try multiple strategies to extract valid JSON from raw response."""
    raw = raw.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Remove markdown code fences
    cleaned = raw
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find JSON object in text
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 4: Fix common issues (trailing commas, single quotes)
    fixed = cleaned.replace("'", '"')
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return None
