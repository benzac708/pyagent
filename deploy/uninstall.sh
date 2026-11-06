#!/usr/bin/env bash
# Uninstall pyagent from VPS.
# Usage: bash deploy/uninstall.sh [--keep-data] [--dry-run]
#   --keep-data: don't delete agent.db or .env
#   --dry-run:   print commands without executing

set -euo pipefail

KEEP_DATA=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --keep-data) KEEP_DATA=true ;;
    --dry-run) DRY_RUN=true ;;
    -h|--help) echo "Usage: $0 [--keep-data] [--dry-run]"; exit 0 ;;
  esac
done

run() {
  if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] $*"
  else
    echo "→ $*"
    bash -c "$*"
  fi
}

echo "=== pyagent uninstaller ==="

# 1. Stop and disable systemd units
echo "--- Stopping services ---"
run "sudo systemctl stop pyagent 2>/dev/null || true"
run "sudo systemctl disable pyagent 2>/dev/null || true"
run "sudo systemctl stop vps-agent-watch.timer 2>/dev/null || true"
run "sudo systemctl disable vps-agent-watch.timer 2>/dev/null || true"
run "sudo systemctl stop vps-actuator 2>/dev/null || true"
run "sudo systemctl disable vps-actuator 2>/dev/null || true"

# 2. Remove systemd unit files
echo "--- Removing systemd units ---"
run "sudo rm -f /etc/systemd/system/pyagent.service"
run "sudo rm -f /etc/systemd/system/pyagent-digest.service"
run "sudo rm -f /etc/systemd/system/pyagent-digest.timer"
run "sudo rm -f /etc/systemd/system/vps-agent-watch.service"
run "sudo rm -f /etc/systemd/system/vps-agent-watch.timer"
run "sudo rm -f /etc/systemd/system/vps-actuator.service"
run "sudo systemctl daemon-reload"

# 3. Stop and remove Docker container + image
echo "--- Removing Docker ---"
run "docker stop pyagent 2>/dev/null || true"
run "docker rm pyagent 2>/dev/null || true"
run "docker rmi pyagent 2>/dev/null || true"

# 4. Remove Caddy config (manual)
echo "--- Caddy ---"
echo "  Manually remove the pyagent.zachara.dev block from your Caddyfile"
echo "  and run: sudo systemctl reload caddy"

# 5. Remove app directory (with sudo for permission issues)
echo "--- App directory ---"
APP_DIR="/opt/pyagent"
if [ "$KEEP_DATA" = true ]; then
  echo "  Keeping data (--keep-data). App code removed, .env and agent.db preserved."
  run "sudo rm -rf ${APP_DIR}/agent ${APP_DIR}/tools ${APP_DIR}/api ${APP_DIR}/tests ${APP_DIR}/deploy ${APP_DIR}/scripts ${APP_DIR}/.github ${APP_DIR}/.venv 2>/dev/null || true"
  run "sudo rm -f ${APP_DIR}/Dockerfile ${APP_DIR}/Makefile ${APP_DIR}/pyproject.toml ${APP_DIR}/README.md ${APP_DIR}/SECURITY.md ${APP_DIR}/.env.example ${APP_DIR}/.pre-commit-config.yaml ${APP_DIR}/.gitignore 2>/dev/null || true"
else
  run "sudo rm -rf ${APP_DIR}"
  echo "  Removed ${APP_DIR} (including agent.db and .env)"
fi

echo ""
echo "=== Uninstall complete ==="
echo "Remaining manual steps:"
echo "  1. Remove pyagent.zachara.dev from Caddyfile + reload caddy"
echo "  2. Remove Tailscale ACLs if any"
echo "  3. Delete GitHub repo if desired: gh repo delete benzac708/pyagent"
EOF
echo "written"