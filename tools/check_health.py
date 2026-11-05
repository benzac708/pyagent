"""Check the health of a known service via its HTTP endpoint (read-only)."""

import urllib.request

from pydantic import BaseModel

_HEALTH_URLS = {
    "pyagent": "http://localhost:8000/health",
}


class CheckHealthInput(BaseModel):
    service: str


def check_health(service: str) -> str:
    """Return health status for a known service. Read-only, no side effects."""
    url = _HEALTH_URLS.get(service)
    if url is None:
        return f"Error: unknown service '{service}'. Known: {', '.join(_HEALTH_URLS)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read().decode()
            return f"service={service} status=healthy http={r.status} body={body[:200]}"
    except Exception as e:
        return f"service={service} status=unhealthy error={e}"
