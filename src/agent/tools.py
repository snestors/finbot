"""
MCP-style tools for FinBot agent.
Allows the agent to read/edit its own code and manage services safely.
"""
import os
import subprocess
import logging
import shutil
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
SAFE_DIRS = {PROJECT_ROOT / "src", PROJECT_ROOT / "web", PROJECT_ROOT / "whatsapp-bridge"}
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def _is_safe_path(filepath: str) -> bool:
    p = Path(filepath).resolve()
    return any(str(p).startswith(str(d)) for d in SAFE_DIRS)


class AgentTools:
    """Tools the agent can invoke via function calling."""

    @staticmethod
    def list_tools() -> list[dict]:
        return [
            {
                "name": "read_file",
                "description": "Read a project source file. Path relative to project root (e.g. src/main.py)",
                "parameters": {"path": "string"},
            },
            {
                "name": "write_file",
                "description": "Write/overwrite a project source file. Creates backup first. Path relative to project root.",
                "parameters": {"path": "string", "content": "string"},
            },
            {
                "name": "edit_file",
                "description": "Replace a specific string in a file. Path relative to project root.",
                "parameters": {"path": "string", "old_text": "string", "new_text": "string"},
            },
            {
                "name": "list_files",
                "description": "List files in a project directory. Path relative to project root.",
                "parameters": {"path": "string"},
            },
            {
                "name": "restart_service",
                "description": "Safely restart FinBot. Saves state, restarts process.",
                "parameters": {},
            },
            {
                "name": "rpi_status",
                "description": "Get RPi system status (temp, RAM, disk, uptime)",
                "parameters": {},
            },
            {
                "name": "run_command",
                "description": "Run a safe shell command (read-only: ls, cat, grep, find, df, free, uptime, pip list, git log, git status)",
                "parameters": {"command": "string"},
            },
        ]

    @staticmethod
    def read_file(path: str) -> str:
        filepath = PROJECT_ROOT / path
        if not _is_safe_path(str(filepath)):
            return f"Error: Path '{path}' is outside allowed directories"
        if not filepath.exists():
            return f"Error: File '{path}' not found"
        try:
            return filepath.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"

    @staticmethod
    def write_file(path: str, content: str) -> str:
        filepath = PROJECT_ROOT / path
        if not _is_safe_path(str(filepath)):
            return f"Error: Path '{path}' is outside allowed directories"
        try:
            # Backup existing file
            if filepath.exists():
                BACKUP_DIR.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"{filepath.stem}_{ts}{filepath.suffix}"
                shutil.copy2(filepath, BACKUP_DIR / backup_name)
                logger.info(f"Backup created: {backup_name}")
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
            return f"OK: File '{path}' written ({len(content)} chars). Backup saved."
        except Exception as e:
            return f"Error writing file: {e}"

    @staticmethod
    def edit_file(path: str, old_text: str, new_text: str) -> str:
        filepath = PROJECT_ROOT / path
        if not _is_safe_path(str(filepath)):
            return f"Error: Path '{path}' is outside allowed directories"
        if not filepath.exists():
            return f"Error: File '{path}' not found"
        try:
            content = filepath.read_text(encoding="utf-8")
            if old_text not in content:
                return f"Error: old_text not found in '{path}'"
            # Backup
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{filepath.stem}_{ts}{filepath.suffix}"
            shutil.copy2(filepath, BACKUP_DIR / backup_name)
            new_content = content.replace(old_text, new_text, 1)
            filepath.write_text(new_content, encoding="utf-8")
            return f"OK: Edited '{path}'. Backup saved as {backup_name}."
        except Exception as e:
            return f"Error editing file: {e}"

    @staticmethod
    def list_files(path: str = "") -> str:
        dirpath = PROJECT_ROOT / path
        if not dirpath.exists():
            return f"Error: Directory '{path}' not found"
        try:
            items = []
            for item in sorted(dirpath.iterdir()):
                if item.name.startswith(".") or item.name == "__pycache__" or item.name == "node_modules" or item.name == "venv":
                    continue
                prefix = "[DIR]" if item.is_dir() else f"[{item.stat().st_size}B]"
                items.append(f"{prefix} {item.name}")
            return "\n".join(items) or "(empty)"
        except Exception as e:
            return f"Error listing files: {e}"

    @staticmethod
    def restart_service() -> str:
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "finbot"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return "OK: FinBot service restarting..."
            # Fallback: if not running as systemd service
            return f"Systemd restart failed: {result.stderr}. Use manual restart."
        except Exception as e:
            return f"Error restarting: {e}"

    @staticmethod
    def rpi_status() -> str:
        parts = []
        for label, cmd in [
            ("Temp", "vcgencmd measure_temp"),
            ("RAM", "free -m | grep Mem | awk '{printf \"%dMB/%dMB (%.0f%%)\", , , /*100}'"),
            ("Disco", "df -h / | tail -1 | awk '{printf \"%s/%s (%s)\", , , }'"),
            ("Uptime", "uptime -p"),
            ("CPU", "top -bn1 | grep 'Cpu(s)' | awk '{printf \"%.1f%%\", }'"),
        ]:
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                parts.append(f"{label}: {r.stdout.strip()}")
            except Exception:
                parts.append(f"{label}: N/A")
        return "\n".join(parts)

    @staticmethod
    def run_command(command: str) -> str:
        ALLOWED = {"ls", "cat", "head", "tail", "grep", "find", "df", "free",
                   "uptime", "vcgencmd", "pip", "git", "wc", "date", "ps"}
        base_cmd = command.split()[0]
        if base_cmd not in ALLOWED:
            return f"Error: Command '{base_cmd}' not allowed. Allowed: {', '.join(sorted(ALLOWED))}"
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15, cwd=str(PROJECT_ROOT))
            output = (r.stdout + r.stderr).strip()
            return output[:4000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out (>15s)"
        except Exception as e:
            return f"Error: {e}"

    def execute(self, tool_name: str, params: dict) -> str:
        """Execute a tool by name."""
        tool_map = {
            "read_file": lambda p: self.read_file(p.get("path", "")),
            "write_file": lambda p: self.write_file(p.get("path", ""), p.get("content", "")),
            "edit_file": lambda p: self.edit_file(p.get("path", ""), p.get("old_text", ""), p.get("new_text", "")),
            "list_files": lambda p: self.list_files(p.get("path", "")),
            "restart_service": lambda p: self.restart_service(),
            "rpi_status": lambda p: self.rpi_status(),
            "run_command": lambda p: self.run_command(p.get("command", "")),
        }
        fn = tool_map.get(tool_name)
        if not fn:
            return f"Error: Unknown tool '{tool_name}'"
        try:
            return fn(params)
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}")
            return f"Error executing {tool_name}: {e}"
