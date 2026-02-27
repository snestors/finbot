"""
Plugin: Ask Claude Code (Opus 4.6)
Consult Claude Code CLI with full permissions — read, write, execute, search.
The only protection: core files are guarded by tools.py (can't self-destruct).
"""
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def register():
    return {
        "tools": {
            "ask_claude": {
                "description": (
                    "Consult Claude Code AI (Opus 4.6) with full system access. "
                    "Can read/write files, run commands, search code, install packages. "
                    "Use when you need help implementing something, debugging, or "
                    "any task you can't solve yourself. "
                    "params: {question: 'how do I...', files: ['src/main.py'] (optional)}"
                ),
                "handler": ask_claude,
            },
        },
        "actions": {},
    }


def ask_claude(params: dict) -> str:
    question = params.get("question", "")
    if not question.strip():
        return "Error: Empty question"

    # Optional file context
    files = params.get("files", [])
    file_context = ""
    if files:
        file_context = f"\nRelevant files to look at: {', '.join(files)}"

    prompt = (
        f"You are helping KYN3D, a FinBot agent running on a Raspberry Pi. "
        f"The project is at {PROJECT_ROOT}. "
        f"You have FULL access — read, write, execute, install. "
        f"Do what needs to be done. Be concise and practical. "
        f"You can edit ANY file including core files. Core files have safety: "
        f"auto git checkpoint + preflight import test + auto-revert if broken. "
        f"Prefer plugins in plugins/*.py for new features (hot-reload, no restart needed). "
        f"Core file edits require restart_service to take effect."
        f"{file_context}\n\n"
        f"Task: {question}"
    )

    cmd = [
        "claude",
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--model", "opus",
        "--no-session-persistence",
    ]

    try:
        logger.info(f"[ask_claude] Querying Opus: {question[:80]}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip() or "No response from Claude"

        if len(output) > 12000:
            output = output[:12000] + "\n... (truncated)"

        logger.info(f"[ask_claude] Got {len(output)} chars response")
        return output

    except subprocess.TimeoutExpired:
        return "Error: Claude Code timed out (>5min). Try a more specific question."
    except FileNotFoundError:
        return "Error: claude CLI not found at expected path"
    except Exception as e:
        logger.error(f"[ask_claude] Error: {e}")
        return f"Error consulting Claude: {e}"
