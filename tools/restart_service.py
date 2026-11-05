"""Restart an allowlisted service via the host actuator (scoped action tool)."""

import json
import os
import urllib.request

from pydantic import BaseModel


class RestartServiceInput(BaseModel):
    service: str


def restart_service(service: str) -> str:
    """Restart a service through the host actuator. Only allowlisted services."""
    url = os.getenv("ACTUATOR_URL", "http://host.docker.internal:8099")
    token = os.getenv("ACTUATOR_TOKEN", "")
    if not token:
        return "Error: ACTUATOR_TOKEN not set"
    try:
        data = json.dumps({"service": service}).encode()
        req = urllib.request.Request(
            f"{url.rstrip('/')}/restart",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode())
            return (
                f"service={body.get('service')} action=restart "
                f"result={body.get('result')} verified={body.get('verified')} "
                f"message={body.get('message', '')}"
            )
    except Exception as e:
        return f"Error: actuator request failed: {e}"
