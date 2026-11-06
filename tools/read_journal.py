"""Read recent journal entries for a systemd unit."""

import subprocess

from pydantic import BaseModel


class ReadJournalInput(BaseModel):
    unit: str
    service: str = ""
    lines: int = 20


def read_journal(unit: str = "", service: str = "", lines: int = 20) -> str:
    """Return the last N journal lines for a systemd unit. Read-only."""
    if not unit and service:
        unit = service
    try:
        r = subprocess.run(
            ["journalctl", "-u", unit, "--no-pager", "-n", str(lines)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = r.stdout.strip()
        if not out:
            return f"No journal entries for {unit}."
        # Truncate to avoid flooding context.
        if len(out) > 2000:
            out = out[-2000:]
        return out
    except FileNotFoundError:
        return "journalctl not available"
    except Exception as e:
        return f"Error: {e}"
