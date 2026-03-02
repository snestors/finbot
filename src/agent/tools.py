"""
MCP-style tools for FinBot agent.
Full system access with Python syntax validation.
"""
import os
import py_compile
import subprocess
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Paths that should NEVER be touched
FORBIDDEN_PATHS = {"/etc/shadow", "/etc/passwd", "/boot/firmware/config.txt"}
FORBIDDEN_PREFIXES = ["/proc", "/sys/firmware"]


def _is_forbidden(filepath: str) -> bool:
    """Block truly dangerous paths. Everything else is allowed."""
    p = str(Path(filepath).resolve())
    if p in FORBIDDEN_PATHS:
        return True
    return any(p.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def _check_python_syntax(content: str) -> str | None:
    """Check Python syntax. Returns error message or None if OK."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as f:
            f.write(content)
            f.flush()
            py_compile.compile(f.name, doraise=True)
        os.unlink(f.name)
        return None
    except py_compile.PyCompileError as e:
        try:
            os.unlink(f.name)
        except Exception:
            pass
        return str(e)


class AgentTools:
    """Tools the agent can invoke. Full RPi access with safety rails."""

    @staticmethod
    def list_tools() -> list[dict]:
        return [
            {"name": "read_file", "description": "Read any file on the system. Absolute or relative path.",
             "parameters": {"path": "string"}},
            {"name": "write_file", "description": "Write/overwrite a file. Python syntax validation.",
             "parameters": {"path": "string", "content": "string"}},
            {"name": "edit_file", "description": "Replace text in a file. Python syntax validation.",
             "parameters": {"path": "string", "old_text": "string", "new_text": "string"}},
            {"name": "list_files", "description": "List files in any directory.",
             "parameters": {"path": "string"}},
            {"name": "run_command", "description": "Run any shell command on the RPi.",
             "parameters": {"command": "string"}},
            {"name": "restart_service", "description": "Restart FinBot service.",
             "parameters": {}},
            {"name": "rpi_status", "description": "Get RPi system status (temp, RAM, disk, uptime, services).",
             "parameters": {}},
            {"name": "install_package", "description": "Install a Python or apt package.",
             "parameters": {"name": "string", "manager": "pip|apt"}},
        ]

    @staticmethod
    def read_file(path: str) -> str:
        filepath = Path(path) if path.startswith("/") else PROJECT_ROOT / path
        if _is_forbidden(str(filepath)):
            return f"Error: Path '{path}' is forbidden"
        if not filepath.exists():
            return f"Error: File '{path}' not found"
        try:
            content = filepath.read_text(encoding="utf-8")
            if len(content) > 15000:
                return content[:15000] + f"\n\n... (truncated, total {len(content)} chars)"
            return content
        except UnicodeDecodeError:
            return f"Error: '{path}' is a binary file"
        except Exception as e:
            return f"Error reading file: {e}"

    @staticmethod
    def write_file(path: str, content: str) -> str:
        filepath = Path(path) if path.startswith("/") else PROJECT_ROOT / path
        if _is_forbidden(str(filepath)):
            return f"Error: Path '{path}' is forbidden"
        try:
            if filepath.suffix == '.py':
                syntax_err = _check_python_syntax(content)
                if syntax_err:
                    return f"Error: Syntax error — NOT written. Fix: {syntax_err}"
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
            return f"OK: '{path}' written ({len(content)} chars)"
        except Exception as e:
            return f"Error writing file: {e}"

    @staticmethod
    def edit_file(path: str, old_text: str, new_text: str) -> str:
        filepath = Path(path) if path.startswith("/") else PROJECT_ROOT / path
        if _is_forbidden(str(filepath)):
            return f"Error: Path '{path}' is forbidden"
        if not filepath.exists():
            return f"Error: File '{path}' not found"
        try:
            content = filepath.read_text(encoding="utf-8")
            if old_text not in content:
                return f"Error: old_text not found in '{path}'. Check exact whitespace/indentation."
            new_content = content.replace(old_text, new_text, 1)
            if filepath.suffix == '.py':
                syntax_err = _check_python_syntax(new_content)
                if syntax_err:
                    return f"Error: Edit would break syntax — NOT saved. Fix: {syntax_err}"
            filepath.write_text(new_content, encoding="utf-8")
            return f"OK: Edited '{path}'"
        except Exception as e:
            return f"Error editing: {e}"

    @staticmethod
    def list_files(path: str = "") -> str:
        dirpath = Path(path) if path.startswith("/") else PROJECT_ROOT / path
        if not dirpath.exists():
            return f"Error: Directory '{path}' not found"
        try:
            items = []
            skip = {".git", "__pycache__", "node_modules", "venv", ".cache"}
            for item in sorted(dirpath.iterdir()):
                if item.name in skip or (item.name.startswith(".") and item.name != ".env"):
                    continue
                prefix = "[DIR]" if item.is_dir() else f"[{item.stat().st_size}B]"
                items.append(f"{prefix} {item.name}")
            return "\n".join(items) or "(empty)"
        except PermissionError:
            return f"Error: Permission denied for '{path}'"
        except Exception as e:
            return f"Error listing files: {e}"

    @staticmethod
    def run_command(command: str) -> str:
        """Run any shell command. No restrictions — the agent is trusted."""
        if not command.strip():
            return "Error: Empty command"
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd", ":(){ :|:& };:"]
        for d in dangerous:
            if d in command:
                return f"Error: Blocked dangerous pattern: {d}"
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=60, cwd=str(PROJECT_ROOT),
            )
            output = (r.stdout + r.stderr).strip()
            if len(output) > 8000:
                output = output[:8000] + "\n... (truncated)"
            return output if output else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out (>60s)"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def restart_service() -> str:
        """Restart FinBot service."""
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "finbot"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return "OK: FinBot restarting..."
            return f"Restart failed: {result.stderr}"
        except Exception as e:
            return f"Error restarting: {e}"

    @staticmethod
    def rpi_status() -> str:
        parts = []
        cmds = [
            ("Temp", "vcgencmd measure_temp"),
            ("RAM", "free -m | grep Mem | awk '{printf \"%dMB/%dMB (%.0f%%)\", $3, $2, $3/$2*100}'"),
            ("Disco", "df -h / | tail -1 | awk '{printf \"%s/%s (%s)\", $3, $2, $5}'"),
            ("Uptime", "uptime -p"),
            ("CPU", "top -bn1 | grep 'Cpu(s)' | awk '{printf \"%.1f%%\", $2}'"),
            ("Servicios", "systemctl is-active finbot cloudflared 2>/dev/null | paste -sd' '"),
        ]
        for label, cmd in cmds:
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                parts.append(f"{label}: {r.stdout.strip()}")
            except Exception:
                parts.append(f"{label}: N/A")
        return "\n".join(parts)

    @staticmethod
    def install_package(name: str, manager: str = "pip") -> str:
        """Install a package via pip or apt."""
        if not name or not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
            return f"Error: Invalid package name '{name}'"
        try:
            if manager == "pip":
                r = subprocess.run(
                    ["pip", "install", name],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(PROJECT_ROOT),
                )
            elif manager == "apt":
                r = subprocess.run(
                    ["sudo", "apt-get", "install", "-y", name],
                    capture_output=True, text=True, timeout=180,
                )
            else:
                return f"Error: Unknown manager '{manager}'. Use pip or apt."
            output = (r.stdout + r.stderr).strip()
            if r.returncode == 0:
                return f"OK: {name} installed via {manager}"
            return f"Error installing {name}: {output[-500:]}"
        except subprocess.TimeoutExpired:
            return "Error: Install timed out"
        except Exception as e:
            return f"Error: {e}"

    def execute(self, tool_name: str, params: dict) -> str:
        """Execute a tool by name."""
        tool_map = {
            "read_file": lambda p: self.read_file(p.get("path", "")),
            "write_file": lambda p: self.write_file(p.get("path", ""), p.get("content", "")),
            "edit_file": lambda p: self.edit_file(p.get("path", ""), p.get("old_text", ""), p.get("new_text", "")),
            "list_files": lambda p: self.list_files(p.get("path", "")),
            "run_command": lambda p: self.run_command(p.get("command", "")),
            "restart_service": lambda p: self.restart_service(),
            "rpi_status": lambda p: self.rpi_status(),
            "install_package": lambda p: self.install_package(p.get("name", ""), p.get("manager", "pip")),
        }
        fn = tool_map.get(tool_name)
        if not fn:
            return f"Error: Unknown tool '{tool_name}'. Available: {', '.join(tool_map.keys())}"
        try:
            return fn(params)
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}")
            return f"Error executing {tool_name}: {e}"
