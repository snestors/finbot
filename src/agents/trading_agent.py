"""Trading agent — monitors and controls the standalone trading bot."""
from src.agents.base_agent import BaseAgent
from src.agents.context_builders import build_trading_context


class TradingAgent(BaseAgent):
    AGENT_NAME = "trading"
    PROMPT_FILE = "trading.md"

    def __init__(self, llm_client, trading_bot=None):
        super().__init__(llm_client)
        self.trading_bot = trading_bot

    async def build_context(self, **kwargs) -> str:
        return build_trading_context(self.trading_bot)
