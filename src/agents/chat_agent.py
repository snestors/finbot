# DEPRECATED: This agent is replaced by unified_agent.py when UNIFIED_AGENT_ENABLED=True.
# Will be removed after unified agent is validated in production.
# See: src/agents/unified_agent.py, data/agents/unified.md
"""Chat/general agent — handles casual conversation, general questions, ideas, planning, and onboarding."""
from src.agents.base_agent import BaseAgent
from src.agents.context_builders import build_chat_context


class ChatAgent(BaseAgent):
    AGENT_NAME = "chat"
    PROMPT_FILE = "chat.md"

    def __init__(self, llm_client, mcp_manager=None):
        super().__init__(llm_client)
        self.mcp_manager = mcp_manager

    async def build_context(self, **kwargs) -> str:
        repos = kwargs.get("repos", {})
        parts = [await build_chat_context(repos)]

        if self.mcp_manager and self.mcp_manager.total_tools > 0:
            parts.append(self.mcp_manager.get_tool_descriptions())

        return "\n".join(parts)
