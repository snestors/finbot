# DEPRECATED: This agent is replaced by unified_agent.py when UNIFIED_AGENT_ENABLED=True.
# Will be removed after unified agent is validated in production.
# See: src/agents/unified_agent.py, data/agents/unified.md
"""Analysis agent — handles financial queries, summaries, budgets, currency conversion."""
from src.agents.base_agent import BaseAgent
from src.agents.context_builders import build_analysis_context


class AnalysisAgent(BaseAgent):
    AGENT_NAME = "analysis"
    PROMPT_FILE = "analysis.md"

    async def build_context(self, **kwargs) -> str:
        repos = kwargs.get("repos", {})
        return await build_analysis_context(repos)
