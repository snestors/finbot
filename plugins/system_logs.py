"""Plugin: system_logs — retrieve FinBot logs from journald with robust fallback."""
import logging
import subprocess

logger = logging.getLogger(__name__)


def register():
    return {
        "tools": {
            "finbot_logs": {
                "description": (
                    "Obtener logs recientes de FinBot. "
                    "params: {lines: 50, filter: 'texto', level: 'ERROR|WARNING|INFO'}"
                ),
                "handler": finbot_logs,
            },
        },
        "actions": {},
    }


def finbot_logs(params: dict) -> str:
    """Retrieve recent FinBot logs from journald."""
    try:
        lines = min(int(params.get("lines", 50)), 200)
    except (ValueError, TypeError):
        lines = 50
    level = str(params.get("level", "")).upper()
    text_filter = str(params.get("filter", ""))

    try:
        cmd = ["journalctl", "-u", "finbot.service", "--no-pager",
               "-n", str(lines * 3), "--output", "short-iso"]

        if level in ("ERROR", "WARNING", "INFO", "DEBUG"):
            prio_map = {"ERROR": "3", "WARNING": "4", "INFO": "6", "DEBUG": "7"}
            cmd.extend(["-p", prio_map[level]])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()

        if not output and result.stderr:
            return f"Error journalctl: {result.stderr.strip()[:200]}"

        if not output:
            return "No se encontraron logs para finbot.service."

        # Apply text filter if provided
        if text_filter:
            filtered = [
                line for line in output.split("\n")
                if text_filter.lower() in line.lower()
            ]
            if not filtered:
                return f"No se encontraron logs con filtro '{text_filter}'. Intenta con otro termino."
            output = "\n".join(filtered[-lines:])
        else:
            log_lines = output.split("\n")
            output = "\n".join(log_lines[-lines:])

        # Truncate if too long for LLM context
        if len(output) > 4000:
            output = output[-4000:]
            output = "...[truncado]\n" + output

        return output

    except FileNotFoundError:
        return "Error: journalctl no encontrado. Verifica que finbot corre como systemd service."
    except subprocess.TimeoutExpired:
        return "Error: timeout obteniendo logs (>10s)"
    except Exception as e:
        logger.error(f"Error getting logs: {e}", exc_info=True)
        return f"Error obteniendo logs: {type(e).__name__}: {e}"
