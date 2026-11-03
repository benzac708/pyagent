"""Run a shell command with a timeout."""

import os
import subprocess

from pydantic import BaseModel

_MAX_OUTPUT = 50_000  # cap output to avoid context/log flooding

# Redact every non-trivial environment value, not just the two API keys.
_SECRET_VALUES = [v for v in os.environ.values() if v and len(v) >= 8]


def _redact(text: str) -> str:
    for secret in _SECRET_VALUES:
        if secret and secret in text:
            text = text.replace(secret, "[REDACTED]")
    return text


class BashInput(BaseModel):
    command: str
    timeout: int = 30


def bash(command: str, timeout: int = 30) -> str:
    """Run a shell command. Returns stdout + stderr. Times out after `timeout`s."""
    if os.getenv("BASH_ENABLED", "true").lower() not in ("1", "true", "yes"):
        return "Error: bash tool is disabled (BASH_ENABLED=false)"
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        result_text = _redact(output.strip() or "(no output)")
        if len(result_text) > _MAX_OUTPUT:
            result_text = result_text[:_MAX_OUTPUT] + f"\n... [truncated at {_MAX_OUTPUT} chars]"
        return result_text
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"
