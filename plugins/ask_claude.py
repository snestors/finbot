"""
Plugin: Ask Claude Code
Consult Claude Code CLI when stuck — can read files, search code, run commands.
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
                    "Consult Claude Code AI for help. It can read project files, "
                    "search code, and run commands. Use when you don't know how to "
                    "do something or need debugging help. "
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
        f"Answer concisely and practically. Include code snippets if relevant. "
        f"Do NOT make changes — only analyze and advise."
        f"{file_context}\n\n"
        f"Question: {question}"
    )

    cmd = [
        "claude",
        "-p", prompt,
        "--allowedTools", "Read Glob Grep Bash(grep:*,find:*,cat:*,ls:*,head:*,tail:*)",
        "--model", "haiku",
        "--no-session-persistence",
    ]

    try:
        logger.info(f"[ask_claude] Querying: {question[:80]}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip() or "No response from Claude"

        if len(output) > 8000:
            output = output[:8000] + "\n... (truncated)"

        logger.info(f"[ask_claude] Got {len(output)} chars response")
        return output

    except subprocess.TimeoutExpired:
        return "Error: Claude Code timed out (>2min). Try a more specific question."
    except FileNotFoundError:
        return "Error: claude CLI not found at expected path"
    except Exception as e:
        logger.error(f"[ask_claude] Error: {e}")
        return f"Error consulting Claude: {e}"
