#!/usr/bin/env python3
"""Config-driven VPS health watcher. Runs cheap checks; invokes the agent only on failure."""

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = os.getenv("WATCH_CONFIG", "/opt/pyagent/watch-checks.json")
STATE_FILE = os.getenv("WATCH_STATE", "/opt/vps-ops/pyagent-restart.state")
AUDIT_LOG = os.getenv("WATCH_AUDIT", "/opt/vps-ops/pyagent-actions.log")
METAPROMPT = os.getenv("WATCH_METAPROMPT", "/opt/pyagent/pending-triage.md")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def check_http(check):
    try:
        with urllib.request.urlopen(check["url"], timeout=5) as r:
            if r.status == check.get("expect_status", 200):
                return None
            return f"{check.get('name', check['url'])}: HTTP {r.status}"
    except Exception as e:
        return f"{check.get('name', check['url'])}: {e}"


def check_disk(check):
    import shutil

    total, used, _ = shutil.disk_usage(check["path"])
    pct = (used / total) * 100 if total else 0
    if pct >= check.get("threshold_pct", 85):
        return f"disk {check['path']} at {pct:.1f}% (threshold {check['threshold_pct']}%)"
    return None


def check_backup(check):
    p = Path(check["path"])
    if not p.exists():
        return f"backup missing: {check['path']}"
    age_h = (time.time() - p.stat().st_mtime) / 3600
    if age_h >= check.get("max_age_hours", 25):
        return f"backup {check['path']} is {age_h:.0f}h old (max {check['max_age_hours']}h)"
    return None


CHECKERS = {"http": check_http, "disk": check_disk, "backup": check_backup}


def circuit_breaker(recent, max_restarts, window):
    now = time.time()
    return sum(1 for ts in recent if now - ts < window) >= max_restarts


def load_recent_restarts():
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


def record_restart():
    with open(STATE_FILE, "a") as f:
        f.write(f"{time.time()}\n")


def audit(msg):
    with open(AUDIT_LOG, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")


def run_checks(config):
    failures = []
    for check in config.get("checks", []):
        checker = CHECKERS.get(check["type"])
        if checker is None:
            failures.append(f"unknown check type: {check['type']}")
            continue
        result = checker(check)
        if result:
            failures.append(result)
    return failures


def try_remediate(failures, config):
    remediation = config.get("remediation", {})
    allowlist = set(remediation.get("restart_allowlist", []))
    max_restarts = remediation.get("max_restarts", 3)
    window = remediation.get("restart_window_seconds", 600)
    recent = load_recent_restarts()

    remediated = []
    for failure in list(failures):
        # Only attempt restart if a known service name appears in the failure
        for svc in allowlist:
            if svc in failure.lower():
                if circuit_breaker(recent, max_restarts, window):
                    failures.append(f"restart circuit breaker tripped for {svc}")
                    audit(f"restart {svc} result=circuit_breaker")
                    continue
                # attempt restart
                try:
                    subprocess.run(["systemctl", "restart", svc], check=True, timeout=30)
                    time.sleep(3)
                    # verify
                    healthy = False
                    for check in config.get("checks", []):
                        if check.get("type") == "http" and check.get("name") == svc:
                            r = check_http(check)
                            healthy = r is None
                            break
                    if healthy:
                        remediated.append(svc)
                        recent.append(time.time())
                        record_restart()
                        audit(f"restart {svc} result=success")
                    else:
                        audit(f"restart {svc} result=failed")
                except Exception as e:
                    audit(f"restart {svc} result=error error={e}")
    for svc in remediated:
        failures = [f for f in failures if svc not in f.lower() or "restarted" in f]
        failures.append(f"{svc} was down and has been restarted")
    return failures


def run_agent(config, failures):
    agent = config.get("agent", {})
    compose_dir = agent.get("compose_dir", "/opt/pyagent")
    container = agent.get("container", "pyagent")
    max_iter = agent.get("max_iterations", 5)
    max_tokens = agent.get("max_tokens", 8000)
    allowed_tools = ",".join(agent.get("allowed_tools", []))
    rf = agent.get("response_format", "json")
    prompt = (
        f"VPS health checks failed: {'; '.join(failures)}. "
        "Call check_health once, then output JSON: {status, findings[], recommendations[], verified}. "
        "Be concise. Do not read additional files."
    )
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-e",
        f"MAX_ITERATIONS={max_iter}",
        "-e",
        f"MAX_TOKENS={max_tokens}",
        "-e",
        f"ALLOWED_TOOLS={allowed_tools}",
        "-e",
        f"RESPONSE_FORMAT={rf}",
        container,
        "uv",
        "run",
        "python",
        "-m",
        "agent",
        prompt,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=compose_dir, timeout=120)
    output = result.stdout + result.stderr
    print(output)
    # parse JSON from output
    import re

    matches = re.findall(r'\{[^{}]*"status"[^{}]*\}', output, re.DOTALL)
    report = None
    for m in reversed(matches):
        try:
            obj = json.loads(m)
            if "status" in obj and "findings" in obj:
                report = obj
                break
        except json.JSONDecodeError:
            continue
    if report:
        print(f"[agent-watch] report: {json.dumps(report)}")
        audit(f"triage report={json.dumps(report)}")
    else:
        print("[agent-watch] no valid JSON report found in agent output")
    # write metaprompt
    with open(METAPROMPT, "w") as f:
        f.write(f"# Pending VPS Triage\n\nDetected: {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write("## Failures\n")
        for fail in failures:
            f.write(f"- {fail}\n")
        f.write("\n## Metaprompt\n")
        f.write("A VPS health check failed. Investigate and produce a JSON digest.\n")
    return report


def main():
    config = load_config()
    failures = run_checks(config)
    if not failures:
        sys.exit(0)
    failures = try_remediate(failures, config)
    # re-check after remediation
    remaining = run_checks(config)
    if not remaining:
        print("[agent-watch] all checks pass after remediation")
        audit("all checks pass after remediation")
        sys.exit(0)
    failures = remaining
    print(f"[agent-watch] failures: {failures}")
    run_agent(config, failures)


if __name__ == "__main__":
    main()
