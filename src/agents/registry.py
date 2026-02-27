"""Agent registry — manages agent instances and provides discovery info."""
import logging
from pathlib import Path

from src.agents.base_agent import BaseAgent, AGENTS_DIR

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Manages registered agent instances."""

    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}

    def register(self, name: str, agent: BaseAgent):
        self.agents[name] = agent
        logger.info(f"Agent registered: {name} ({agent.PROMPT_FILE})")

    def get(self, name: str) -> BaseAgent | None:
        return self.agents.get(name)

    def list_agents(self) -> list[dict]:
        """List all registered agents with prompt file info."""
        result = []
        for name, agent in self.agents.items():
            prompt_path = AGENTS_DIR / agent.PROMPT_FILE
            result.append({
                "name": name,
                "prompt_file": agent.PROMPT_FILE,
                "prompt_exists": prompt_path.exists(),
                "prompt_size": prompt_path.stat().st_size if prompt_path.exists() else 0,
            })
        return result

    def reload_all(self):
        """Force reload all agent prompts on next call."""
        for agent in self.agents.values():
            agent._prompt_cache = None
        logger.info("All agent prompts marked for reload")
