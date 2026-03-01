"""Admin agent — manages system tools, memory, reminders, profile, and other agents."""
from src.agents.base_agent import BaseAgent
from src.agents.context_builders import build_admin_context


class AdminAgent(BaseAgent):
    AGENT_NAME = "admin"
    PROMPT_FILE = "admin.md"

    def __init__(self, llm_client, registry=None, mcp_manager=None):
        super().__init__(llm_client)
        self.registry = registry
        self.mcp_manager = mcp_manager

    async def build_context(self, **kwargs) -> str:
        repos = kwargs.get("repos", {})
        registry_info = self.registry.list_agents() if self.registry else None
        mcp_tools = ""
        if self.mcp_manager and self.mcp_manager.total_tools > 0:
            mcp_tools = self.mcp_manager.get_tool_descriptions()
        return await build_admin_context(repos, registry_info=registry_info,
                                         mcp_tools=mcp_tools)
