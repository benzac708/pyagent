"""Check whether systemd services are active."""

import subprocess

from pydantic import BaseModel


class CheckServicesInput(BaseModel):
    services: list[str]


def check_services(services: list[str]) -> str:
    """Return active/inactive status for each named service."""
    lines = []
    for svc in services:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True,
                text=True,
                timeout=5,
            )
            state = r.stdout.strip() or r.stderr.strip() or "unknown"
            lines.append(f"{svc}: {state}")
        except FileNotFoundError:
            lines.append(f"{svc}: systemctl not available")
        except Exception as e:
            lines.append(f"{svc}: Error: {e}")
    return "\n".join(lines)
