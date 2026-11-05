"""Restart an allowlisted service via the host actuator (scoped action tool)."""

import json
import os
import urllib.request

from pydantic import BaseModel


class RestartServiceInput(BaseModel):
    service: str


def restart_service(service: str) -> str:
    """Restart a service through the host actuator. Only allowlisted services."""
    token = os.getenv("ACTUATOR_TOKEN", "")
    if not token:
        return "Error: ACTUATOR_TOKEN not set"
    socket_path = os.getenv("ACTUATOR_SOCKET", "")
    data = json.dumps({"service": service}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    try:
        if socket_path:
            import http.client
            import socket as _socket

            class UnixHTTPConnection(http.client.HTTPConnection):
                def connect(self):
                    self.sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
                    self.sock.settimeout(30)
                    self.sock.connect(socket_path)

            conn = UnixHTTPConnection(socket_path)
            conn.request("POST", "/restart", body=data, headers=headers)
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
            conn.close()
        else:
            url = os.getenv("ACTUATOR_URL", "http://host.docker.internal:8099")
            req = urllib.request.Request(f"{url.rstrip('/')}/restart", data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode())
        return (
            f"service={body.get('service')} action=restart "
            f"result={body.get('result')} verified={body.get('verified')} "
            f"message={body.get('message', '')}"
        )
    except Exception as e:
        return f"Error: actuator request failed: {e}"
