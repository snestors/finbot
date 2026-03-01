"""LLM client: Claude (primary via OAuth) + Gemini (fallback)."""
import asyncio
import logging
from dataclasses import dataclass

import anthropic
from google import genai

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str  # "sonnet" or "gemini"


class LLMClient:
    """Anthropic Claude as primary, Google Gemini as fallback."""

    def __init__(self, claude_token: str = "", gemini_client: genai.Client = None,
                 claude_model: str = "claude-sonnet-4-20250514"):
        self._claude: anthropic.AsyncClient | None = None
        self._gemini = gemini_client
        self._claude_model = claude_model

        if claude_token:
            if claude_token.startswith("sk-ant-oat"):
                # OAuth token
                self._claude = anthropic.AsyncClient(auth_token=claude_token, api_key="")
                logger.info(f"[llm] Claude client ready via OAuth (model={claude_model})")
            else:
                # Standard API key
                self._claude = anthropic.AsyncClient(api_key=claude_token)
                logger.info(f"[llm] Claude client ready via API key (model={claude_model})")

        if gemini_client:
            logger.info("[llm] Gemini client ready (fallback)")

    async def generate(self, system: str, user_message: str,
                       history: list[dict] | None = None) -> LLMResponse:
        """Generate response. Claude first with retries, Gemini fallback."""
        if self._claude:
            # Retry Claude up to 3 times on rate limit (wait 5s, 10s, 15s)
            for attempt in range(3):
                try:
                    text = await self._call_claude(system, user_message, history)
                    return LLMResponse(text=text, model="sonnet")
                except anthropic.AuthenticationError as e:
                    logger.warning(f"[llm] Claude AuthError: {e} -> Gemini fallback")
                    break  # No point retrying auth errors
                except anthropic.RateLimitError as e:
                    wait = 5 * (attempt + 1)
                    if attempt < 2:
                        logger.info(f"[llm] Claude 429, retrying in {wait}s (attempt {attempt + 1}/3)")
                        await asyncio.sleep(wait)
                    else:
                        logger.warning(f"[llm] Claude 429 after 3 attempts -> Gemini fallback")
                except anthropic.APIError as e:
                    logger.error(f"[llm] Claude APIError: {e} -> Gemini fallback")
                    break

        if self._gemini:
            text = await self._call_gemini(system, user_message, history)
            return LLMResponse(text=text, model="gemini")

        raise RuntimeError("No LLM client available (Claude + Gemini both failed)")

    async def _call_claude(self, system: str, user_message: str,
                           history: list[dict] | None) -> str:
        messages = self._build_claude_messages(user_message, history)
        response = await self._claude.messages.create(
            model=self._claude_model,
            max_tokens=16384,
            system=system,
            messages=messages,
            extra_headers={"anthropic-beta": "oauth-2025-04-20"},
        )
        text = response.content[0].text
        logger.debug(f"[llm] Claude OK ({response.usage.input_tokens}in/{response.usage.output_tokens}out)")
        return text

    async def _call_gemini(self, system: str, user_message: str,
                           history: list[dict] | None) -> str:
        prompt = self._build_gemini_prompt(system, user_message, history)
        response = await self._gemini.aio.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt,
        )
        logger.debug("[llm] Gemini fallback OK")
        return response.text

    def _build_claude_messages(self, user_message: str,
                               history: list[dict] | None) -> list[dict]:
        """Build Claude messages array. Ensures valid alternation."""
        messages = []
        if history:
            for msg in history:
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

    _GEMINI_GUARD = """## REGLAS CRITICAS (OBLIGATORIO)
- NUNCA digas que hiciste algo si no incluiste la accion en el JSON de "acciones".
- Si no ejecutas una accion, NO confirmes que se hizo. Di "no pude hacerlo" o genera la accion correcta.
- Tu respuesta SIEMPRE debe ser JSON valido con "respuesta" y "acciones". Sin excepciones.
- PROHIBIDO inventar resultados. Solo reporta lo que realmente ejecutaste.
- Si no sabes el ID de un recurso, pregunta. NO adivines.
"""

    def _build_gemini_prompt(self, system: str, user_message: str,
                             history: list[dict] | None) -> str:
        """Build single-string prompt for Gemini."""
        parts = [self._GEMINI_GUARD, system]
        if history:
            parts.append("\n## HISTORIAL (ultimos mensajes)")
            for msg in history:
                role = "Usuario" if msg.get("role") == "user" else "KYN3D"
                content = msg.get("content", "")
                if content:
                    if role == "KYN3D" and len(content) > 1500:
                        content = content[:1000] + "\n...(truncado)...\n" + content[-500:]
                    parts.append(f"{role}: {content}")
        parts.append(f'\nUsuario: "{user_message}"')
        return "\n".join(parts)
