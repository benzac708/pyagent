"""Run a shell command with a timeout."""

import subprocess

from pydantic import BaseModel


class BashInput(BaseModel):
    command: str
    timeout: int = 30


def bash(command: str, timeout: int = 30) -> str:
    """Run a shell command. Returns stdout + stderr. Times out after `timeout` seconds."""
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
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"
