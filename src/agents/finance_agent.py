"""Finance agent — handles expenses, income, payments, transfers, debts, cobros."""
from src.agents.base_agent import BaseAgent
from src.agents.context_builders import build_finance_context


class FinanceAgent(BaseAgent):
    AGENT_NAME = "finance"
    PROMPT_FILE = "finance.md"

    async def build_context(self, **kwargs) -> str:
        repos = kwargs.get("repos", {})
        return await build_finance_context(repos)
