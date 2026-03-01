"""Generic MCP client manager — connects to N MCP servers, discovers tools, routes calls."""
import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


def _expand_env(value: str) -> str:
    """Expand ${VAR} references in a string using os.environ."""
    if not isinstance(value, str) or "${" not in value:
        return value
    import re
    return re.sub(r'\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), ""), value)


class MCPManager:
    """Generic MCP client — manages connections to multiple MCP servers."""

    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tools_cache: dict[str, list] = {}  # server_name → [mcp.types.Tool]
        self._tool_to_server: dict[str, str] = {}  # tool_name → server_name

    async def connect_from_config(self, config_path: str):
        """Load server definitions from JSON config and connect all enabled servers."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"[mcp] Config not found: {config_path}")
            return

        try:
            servers = json.loads(path.read_text())
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[mcp] Invalid config {config_path}: {e}")
            return

        async def _safe_connect(server):
            try:
                await self.connect_server(
                    name=server["name"],
                    command=_expand_env(server["command"]),
                    args=[_expand_env(a) for a in server.get("args", [])],
                    env={k: _expand_env(v) for k, v in server.get("env", {}).items()},
                )
            except Exception as e:
                logger.error(f"[mcp] Failed to connect '{server.get('name')}': {e}")

        tasks = []
        for server in servers:
            if not server.get("enabled", True):
                logger.info(f"[mcp] Skipping disabled server: {server.get('name', '?')}")
                continue
            tasks.append(_safe_connect(server))

        if tasks:
            await asyncio.gather(*tasks)

    async def connect_server(self, name: str, command: str,
                             args: list[str], env: dict = None):
        """Connect to a single MCP server via stdio."""
        # Merge env with current environment so the subprocess inherits PATH etc.
        full_env = {**os.environ}
        if env:
            full_env.update({k: v for k, v in env.items() if v})

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=full_env,
        )

        transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = transport

        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        # Discover tools
        response = await session.list_tools()
        self._sessions[name] = session
        self._tools_cache[name] = response.tools

        # Build tool_name → server_name mapping
        for tool in response.tools:
            if tool.name in self._tool_to_server:
                logger.warning(
                    f"[mcp] Tool '{tool.name}' from '{name}' shadows "
                    f"existing tool from '{self._tool_to_server[tool.name]}'"
                )
            self._tool_to_server[tool.name] = name

        tool_names = [t.name for t in response.tools]
        logger.info(f"[mcp] Connected to '{name}': {len(tool_names)} tools — {tool_names}")

    def get_all_tools(self) -> list[dict]:
        """Get all MCP tools in Claude-compatible format."""
        tools = []
        for server_name, tool_list in self._tools_cache.items():
            for t in tool_list:
                tools.append({
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema or {"type": "object", "properties": {}},
                })
        return tools

    def get_tools(self, server_name: str) -> list[dict]:
        """Get tools from a specific server in Claude-compatible format."""
        tools = []
        for t in self._tools_cache.get(server_name, []):
            tools.append({
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema or {"type": "object", "properties": {}},
            })
        return tools

    def has_tool(self, tool_name: str) -> bool:
        """Check if any connected MCP server provides this tool."""
        return tool_name in self._tool_to_server

    def get_tool_descriptions(self) -> str:
        """Formatted string of all MCP tools for inclusion in system prompts."""
        tools = self.get_all_tools()
        if not tools:
            return ""
        lines = ["Herramientas MCP disponibles (usa tipo=<nombre_tool> en acciones):"]
        for t in tools:
            desc = t.get("description", "sin descripcion")
            params = t.get("input_schema", {}).get("properties", {})
            param_list = []
            for pname, pinfo in params.items():
                req = " (requerido)" if pname in t.get("input_schema", {}).get("required", []) else ""
                param_list.append(f"{pname}{req}")
            param_str = f" — params: {', '.join(param_list)}" if param_list else ""
            lines.append(f"  - {t['name']}: {desc}{param_str}")
        return "\n".join(lines)

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool on the appropriate MCP server. Returns result text."""
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            raise ValueError(f"No MCP server provides tool '{tool_name}'")

        session = self._sessions.get(server_name)
        if not session:
            raise ValueError(f"MCP server '{server_name}' not connected")

        logger.info(f"[mcp] Calling {server_name}/{tool_name} with {arguments}")
        result = await session.call_tool(tool_name, arguments)

        # Extract text from result content
        texts = []
        for item in result.content:
            if hasattr(item, "text"):
                texts.append(item.text)
            elif hasattr(item, "data"):
                texts.append(f"[binary data: {getattr(item, 'mimeType', 'unknown')}]")

        output = "\n".join(texts) if texts else str(result)

        if result.isError:
            logger.warning(f"[mcp] Tool {tool_name} returned error: {output}")
        else:
            logger.debug(f"[mcp] Tool {tool_name} OK: {output[:200]}")

        return output

    @property
    def connected_servers(self) -> list[str]:
        """List names of connected MCP servers."""
        return list(self._sessions.keys())

    @property
    def total_tools(self) -> int:
        """Total number of tools across all servers."""
        return sum(len(tools) for tools in self._tools_cache.values())

    async def close(self):
        """Disconnect all MCP servers."""
        try:
            await self._exit_stack.aclose()
            logger.info(f"[mcp] All servers disconnected")
        except Exception as e:
            logger.error(f"[mcp] Error closing: {e}")
        self._sessions.clear()
        self._tools_cache.clear()
        self._tool_to_server.clear()
