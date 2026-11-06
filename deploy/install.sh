#!/usr/bin/env bash
# Install pyagent on VPS.
# Usage: bash deploy/install.sh [--skip-docker] [--skip-systemd] [--dry-run]
#   --skip-docker:   don't build/run Docker container
#   --skip-systemd:  don't install systemd units
#   --dry-run:       print commands without executing

set -euo pipefail

SKIP_DOCKER=false
SKIP_SYSTEMD=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --skip-docker) SKIP_DOCKER=true ;;
    --skip-systemd) SKIP_SYSTEMD=true ;;
    --dry-run) DRY_RUN=true ;;
    -h|--help) echo "Usage: $0 [--skip-docker] [--skip-systemd] [--dry-run]"; exit 0 ;;
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

APP_DIR="/opt/pyagent"
REPO_URL="https://github.com/benzac708/pyagent.git"

echo "=== pyagent installer ==="

# 1. Clone repo
echo "--- Cloning repo ---"
if [ -d "$APP_DIR" ]; then
  echo "  $APP_DIR already exists. Pulling latest..."
  run "cd $APP_DIR && git pull origin main"
else
  run "sudo git clone $REPO_URL $APP_DIR"
  run "sudo chown -R ubuntu:ubuntu $APP_DIR"
fi

# 2. Configure .env
echo "--- Configuring .env ---"
if [ ! -f "$APP_DIR/.env" ]; then
  run "cp $APP_DIR/.env.example $APP_DIR/.env"
  run "chmod 600 $APP_DIR/.env"
  echo "  ⚠️  Edit $APP_DIR/.env with your API key before starting!"
else
  echo "  .env already exists, skipping."
fi

# 3. Install uv (if not present)
echo "--- Checking uv ---"
if ! command -v uv &>/dev/null; then
  run "curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# 4. Install dependencies
echo "--- Installing dependencies ---"
run "cd $APP_DIR && uv sync --all-extras"

# 5. Build Docker image
if [ "$SKIP_DOCKER" = false ]; then
  echo "--- Building Docker image ---"
  run "cd $APP_DIR && docker build -t pyagent ."
  echo "--- Starting Docker container ---"
  run "docker stop pyagent 2>/dev/null || true"
  run "docker rm pyagent 2>/dev/null || true"
  run "docker run -d --name pyagent --env-file $APP_DIR/.env -p 8000:8000 --restart unless-stopped pyagent"
fi

# 6. Install systemd units
if [ "$SKIP_SYSTEMD" = false ]; then
  echo "--- Installing systemd units ---"
  run "sudo cp $APP_DIR/deploy/pyagent.service /etc/systemd/system/"
  run "sudo cp $APP_DIR/deploy/vps-agent-watch.service /etc/systemd/system/"
  run "sudo cp $APP_DIR/deploy/vps-agent-watch.timer /etc/systemd/system/"
  run "sudo cp $APP_DIR/deploy/vps-actuator.service /etc/systemd/system/"
  run "sudo systemctl daemon-reload"
  run "sudo systemctl enable pyagent"
  run "sudo systemctl start pyagent"
  run "sudo systemctl enable vps-agent-watch.timer"
  run "sudo systemctl start vps-agent-watch.timer"
  run "sudo systemctl enable vps-actuator"
  run "sudo systemctl start vps-actuator"
fi

# 7. Verify
echo "--- Verifying ---"
run "sleep 2"
run "curl -s http://localhost:8000/health || echo 'Health check failed'"

echo ""
echo "=== Install complete ==="
echo "Remaining manual steps:"
echo "  1. Edit $APP_DIR/.env with your API key (if not done)"
echo "  2. Add pyagent.zachara.dev to Caddyfile + reload caddy"
echo "  3. Set up Tailscale ACLs if needed"
echo ""
echo "Useful commands:"
echo "  systemctl status pyagent"
echo "  journalctl -u pyagent -f"
echo "  curl http://localhost:8000/health"
