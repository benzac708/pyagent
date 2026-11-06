"""List failed systemd units on the host."""

import subprocess

from pydantic import BaseModel


class CheckFailedServicesInput(BaseModel):
    pass


def check_failed_services() -> str:
    """Return all failed systemd units. Read-only."""
    try:
        r = subprocess.run(
            ["systemctl", "--failed", "--no-pager", "--no-legend"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = r.stdout.strip()
        if not out:
            return "No failed units."
        return out
    except FileNotFoundError:
        return "systemctl not available"
    except Exception as e:
        return f"Error: {e}"
