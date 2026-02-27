"""
Plugin Manager — dynamic loading of agent plugins.
Plugins live in /plugins/*.py and can define tools and actions.
Hot-reload supported: plugins are reloaded when their file changes.

Plugin template:
    def register():
        return {
            "tools": {"tool_name": {"description": "...", "handler": fn}},
            "actions": {"action_name": handler_fn},
        }
"""
import importlib.util
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).parent.parent.parent / "plugins"


class PluginManager:
    def __init__(self):
        self.tools: dict[str, dict] = {}       # name -> {description, handler}
        self.actions: dict[str, callable] = {}  # name -> async handler(accion, repos)
        self._mtimes: dict[str, float] = {}     # file -> last mtime

    def load_all(self):
        """Load all plugins from plugins/ directory."""
        PLUGINS_DIR.mkdir(exist_ok=True)
        loaded = 0
        for py_file in sorted(PLUGINS_DIR.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                self._load_plugin(py_file)
                loaded += 1
            except Exception as e:
                logger.error(f"Failed to load plugin {py_file.name}: {e}")
        logger.info(f"Loaded {loaded} plugins, {len(self.tools)} tools, {len(self.actions)} actions")

    def reload_all(self):
        """Reload plugins that have changed."""
        PLUGINS_DIR.mkdir(exist_ok=True)
        for py_file in sorted(PLUGINS_DIR.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                mtime = py_file.stat().st_mtime
                if py_file.name not in self._mtimes or mtime > self._mtimes[py_file.name]:
                    self._load_plugin(py_file)
                    logger.info(f"Reloaded plugin: {py_file.name}")
            except Exception as e:
                logger.error(f"Failed to reload plugin {py_file.name}: {e}")

    def _load_plugin(self, path: Path):
        """Load a single plugin file."""
        spec = importlib.util.spec_from_file_location(f"plugin_{path.stem}", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._mtimes[path.name] = path.stat().st_mtime

        if not hasattr(module, "register"):
            logger.warning(f"Plugin {path.name} has no register() function, skipping")
            return

        reg = module.register()
        if not isinstance(reg, dict):
            logger.warning(f"Plugin {path.name} register() didn't return dict, skipping")
            return

        # Register tools
        for name, tool_def in reg.get("tools", {}).items():
            self.tools[name] = tool_def
            logger.debug(f"Registered tool: {name} (from {path.name})")

        # Register actions
        for name, handler in reg.get("actions", {}).items():
            self.actions[name] = handler
            logger.debug(f"Registered action: {name} (from {path.name})")

    def get_tool_handler(self, name: str):
        """Get a tool handler by name."""
        tool = self.tools.get(name)
        return tool["handler"] if tool else None

    def get_action_handler(self, name: str):
        """Get an action handler by name."""
        return self.actions.get(name)

    def list_plugin_tools(self) -> list[dict]:
        """List all plugin tools with descriptions."""
        return [
            {"name": name, "description": tool.get("description", "")}
            for name, tool in self.tools.items()
        ]

    def list_plugin_actions(self) -> list[str]:
        """List all plugin action names."""
        return list(self.actions.keys())
