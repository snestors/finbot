import subprocess
import logging

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "grep", "find", "date",
    "df", "free", "uptime", "vcgencmd",
}


class BashExecutor:
    async def run(self, command: str) -> str:
        base_cmd = command.split()[0]
        if base_cmd not in ALLOWED_COMMANDS:
            return f"Comando '{base_cmd}' no permitido"
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=10,
            )
            return result.stdout or result.stderr
        except subprocess.TimeoutExpired:
            return "Timeout (>10s)"

    async def rpi_health(self) -> str:
        parts = []
        for label, cmd in [
            ("Temp", "vcgencmd measure_temp"),
            ("RAM", "free -m | grep Mem | awk '{printf \"%dMB/%dMB (%.0f%%)\", $3, $2, $3/$2*100}'"),
            ("Disco", "df -h / | tail -1 | awk '{printf \"%s/%s (%s)\", $3, $2, $5}'"),
            ("Uptime", "uptime -p"),
        ]:
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                parts.append(f"{label}: {r.stdout.strip()}")
            except Exception:
                parts.append(f"{label}: N/A")
        return "RPi Status\n" + "\n".join(parts)
