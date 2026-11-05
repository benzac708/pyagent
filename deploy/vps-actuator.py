#!/usr/bin/env python3
"""Host-side actuator for scoped auto-remediation.

Runs on the VPS host (not in a container). Accepts requests from the
pyagent container via host.docker.internal:8099. Only allowlisted
services can be restarted. All actions are logged and circuit-breaker
protected.

Usage: python3 vps-actuator.py
Env: ACTUATOR_TOKEN (required), ACTUATOR_PORT (default 8099),
     ACTUATOR_ALLOWLIST (comma-separated, default "pyagent"),
     ACTUATOR_MAX_RESTARTS (default 3), ACTUATOR_WINDOW (default 600)
"""

import http.server
import json
import os
import socket
import socketserver
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

PORT = int(os.getenv("ACTUATOR_PORT", "8099"))
TOKEN = os.getenv("ACTUATOR_TOKEN", "")
ALLOWLIST = [s.strip() for s in os.getenv("ACTUATOR_ALLOWLIST", "pyagent").split(",") if s.strip()]
MAX_RESTARTS = int(os.getenv("ACTUATOR_MAX_RESTARTS", "3"))
WINDOW = int(os.getenv("ACTUATOR_WINDOW", "600"))
STATE_FILE = os.getenv("ACTUATOR_STATE", "/opt/vps-ops/actuator-restart.state")
AUDIT_LOG = os.getenv("ACTUATOR_AUDIT", "/opt/vps-ops/actuator-actions.log")

HEALTH_URLS = {
    "pyagent": "http://localhost:8000/health",
}


def audit(msg):
    os.makedirs(os.path.dirname(AUDIT_LOG) or ".", exist_ok=True)
    with open(AUDIT_LOG, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")


def recent_restarts():
    if not os.path.exists(STATE_FILE):
        return []
    out = []
    with open(STATE_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(float(line))
                except ValueError:
                    pass
    return out


def do_restart(service):
    if service not in ALLOWLIST:
        return {
            "service": service,
            "result": "denied",
            "verified": False,
            "message": f"service '{service}' not in allowlist {ALLOWLIST}",
        }
    recent = [ts for ts in recent_restarts() if time.time() - ts < WINDOW]
    if len(recent) >= MAX_RESTARTS:
        audit(f"restart {service} result=circuit_breaker ({len(recent)} in {WINDOW}s)")
        return {
            "service": service,
            "result": "circuit_breaker",
            "verified": False,
            "message": f"max {MAX_RESTARTS} restarts in {WINDOW}s exceeded",
        }
    try:
        subprocess.run(["systemctl", "restart", service], check=True, timeout=30)
        time.sleep(3)
        # verify
        url = HEALTH_URLS.get(service)
        healthy = False
        if url:
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    healthy = r.status == 200
            except Exception:
                healthy = False
        os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
        with open(STATE_FILE, "a") as f:
            f.write(f"{time.time()}\n")
        result = "success" if healthy else "failed"
        audit(f"restart {service} result={result} verified={healthy}")
        return {
            "service": service,
            "result": result,
            "verified": healthy,
            "message": f"restarted {service}, health={'ok' if healthy else 'still down'}",
        }
    except Exception as e:
        audit(f"restart {service} result=error error={e}")
        return {"service": service, "result": "error", "verified": False, "message": str(e)}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "allowlist": ALLOWLIST}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):  # noqa: N802
        if self.path != "/restart":
            self.send_response(404)
            self.end_headers()
            return
        auth = self.headers.get("Authorization", "")
        if not TOKEN or auth != f"Bearer {TOKEN}":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        service = body.get("service", "")
        result = do_restart(service)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, fmt, *args):
        pass  # suppress default logging


if __name__ == "__main__":
    if not TOKEN:
        print("ACTUATOR_TOKEN is required", file=__import__("sys").stderr)
        raise SystemExit(1)
    SOCKET_PATH = os.getenv("ACTUATOR_SOCKET", "")
    if SOCKET_PATH:

        class UnixHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            address_family = socket.AF_UNIX

            def server_bind(self):
                if os.path.exists(SOCKET_PATH):
                    os.unlink(SOCKET_PATH)
                super().server_bind()
                os.chmod(SOCKET_PATH, 0o666)

        server = UnixHTTPServer(SOCKET_PATH, Handler)
        print(f"actuator listening on unix:{SOCKET_PATH}, allowlist={ALLOWLIST}")
    else:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        print(f"actuator listening on 127.0.0.1:{PORT}, allowlist={ALLOWLIST}")
    server.serve_forever()
