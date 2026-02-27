"""Chat agent — handles casual conversation, onboarding, ambiguous messages."""
from src.agents.base_agent import BaseAgent
from src.agents.context_builders import build_chat_context


class ChatAgent(BaseAgent):
    AGENT_NAME = "chat"
    PROMPT_FILE = "chat.md"

    async def build_context(self, **kwargs) -> str:
        repos = kwargs.get("repos", {})
        return await build_chat_context(repos)
