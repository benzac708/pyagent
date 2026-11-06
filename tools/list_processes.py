"""List top processes by CPU or memory usage."""

import subprocess

from pydantic import BaseModel


class ListProcessesInput(BaseModel):
    sort_by: str = "cpu"
    count: int = 10


def list_processes(sort_by: str = "cpu", count: int = 10) -> str:
    """Return top processes by CPU or memory. Read-only."""
    sort_flag = "-%cpu" if sort_by == "cpu" else "-%mem"
    try:
        r = subprocess.run(
            ["ps", "aux", "--sort", sort_flag],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = r.stdout.strip().split("\n")
        # Header + top N processes
        header = lines[0]
        top = lines[1 : count + 1]
        out = header + "\n" + "\n".join(top)
        if len(out) > 2000:
            out = out[:2000]
        return out
    except FileNotFoundError:
        return "ps not available"
    except Exception as e:
        return f"Error: {e}"
