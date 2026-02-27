"""Analysis agent — handles financial queries, summaries, budgets, currency conversion."""
from src.agents.base_agent import BaseAgent
from src.agents.context_builders import build_analysis_context


class AnalysisAgent(BaseAgent):
    AGENT_NAME = "analysis"
    PROMPT_FILE = "analysis.md"

    async def build_context(self, **kwargs) -> str:
        repos = kwargs.get("repos", {})
        return await build_analysis_context(repos)
