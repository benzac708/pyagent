# pyagent

A minimal, self-hosted VPS triage agent that diagnoses failures and proposes fixes within hard safety rails.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## What is this?

- **One job, one loop, minimal toolset** - checks VPS health, produces a structured JSON digest, and stops. No multi-agent orchestration, no framework bloat.
- **Config-driven** - all checks, thresholds, and allowlists live in `watch-checks.json`. Adding a new check is a JSON edit, not a code change.
- **Rails in code, not in prompts** - tool allowlists, path denylists, token/iteration caps, and JSON schema validation are enforced by the runtime. The LLM can't override them.
- **Clone-and-run** - `cp .env.example .env`, fill 3 values, `docker compose up`. Working agent in 60 seconds.
- **Mock mode** - `MOCK_LLM=true` needs no API key; explore the CLI, tools, and tests without any external service.

## Quickstart

```bash
git clone https://github.com/benzac708/pyagent && cd pyagent
cp .env.example .env          # add your API key
uv venv && uv sync --all-extras
uv run python -m agent "hello, what can you do?"   # MOCK_LLM=true works without a key
uv run pytest -v && uv run ruff check . && uv run mypy agent/ tools/ api/
```

## Prerequisites

| Requirement | Version |
|---|---|
| Python | >=3.10, <3.13 |
| uv | latest |
| Docker | latest (for deployment) |

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_KEY` | Yes (unless `MOCK_LLM=true`) | - | OpenAI-compatible API key |
| `BASE_URL` | No | `https://api.openai.com/v1` | LLM provider base URL |
| `MODEL` | No | `gpt-4o-mini` | Model name |
| `FALLBACK_BASE_URL` | No | - | Fallback provider URL (e.g., Groq) |
| `FALLBACK_API_KEY` | No | - | Fallback provider API key |
| `FALLBACK_MODEL` | No | - | Fallback model name |
| `DB_PATH` | No | `agent.db` | SQLite database path |
| `MAX_ITERATIONS` | No | `10` | Hard cap on agent loop iterations |
| `MAX_TOKENS` | No | `50000` | Hard cap on total tokens per run |
| `MAX_OUTPUT_RETRIES` | No | `2` | Retries on invalid JSON output |
| `RESPONSE_FORMAT` | No | - | Set to `json` to enforce JSON output |
| `ALLOWED_TOOLS` | No | (all) | Comma-separated tool allowlist |
| `MOCK_LLM` | No | `false` | Set to `true` for demo mode (no API key) |
| `LOG_LEVEL` | No | `info` | Log level |

## Architecture

The agent runs an **Observe → Think → Act → Observe** loop. Each tool call is paired with a result (even on error). Runs are bounded by `MAX_ITERATIONS` and `MAX_TOKENS`.

### Tools

| Tool | Safety | Description |
|---|---|---|
| `read_file` | read-only | Read file contents (path denylist blocks secrets) |
| `list_files` | read-only | List files and directories |
| `check_disk` | read-only | Disk usage for a path |
| `check_backups` | read-only | Backup file existence and age |
| `check_health` | read-only | HTTP health check for a URL |
| `list_runs` | read-only | Query the agent's own run history |
| `bash` | mutating | Run a shell command (timeout enforced) |
| `edit_file` | mutating | Write content to a file |

Safety tiers: `read-only` (no approval needed), `mutating` (allowlisted in production).

### Watcher (VPS health monitor)

The watcher (`deploy/vps-agent-watch.py`) runs cheap checks every 5 minutes. If any fail, it invokes the agent with a structured prompt. The agent diagnoses and produces a JSON digest. The watcher logs everything to an append-only audit trail.

Configure checks in `watch-checks.json`:
```json
{
  "checks": [
    {"type": "http", "name": "pyagent", "url": "http://localhost:8000/health", "expect_status": 200},
    {"type": "disk", "path": "/", "threshold_pct": 85},
    {"type": "backup", "path": "/home/ubuntu/backups/jobs/jobs.db", "max_age_hours": 25}
  ]
}
```

## Safety & Guardrails

- **Tool allowlist:** `ALLOWED_TOOLS` filters the registry at import time. Unregistered tools don't exist.
- **Path denylist:** `read_file` blocks `.env`, `*.key`, `*.pem`, `*secret*`, `*password*`, `id_rsa`, `token`.
- **Cost caps:** `MAX_ITERATIONS` and `MAX_TOKENS` are hard stops, not suggestions.
- **JSON schema enforcement:** `RESPONSE_FORMAT=json` validates output shape; invalid output is retried or rejected.
- **Circuit breaker:** The watcher stops after N restarts in T minutes and escalates.
- **Audit log:** Append-only log of every action, diagnosis, and verification.
- **Human-in-the-loop:** Tier 2+ actions (config edits, scaling) require human approval. The agent recommends; you decide.

See `SECURITY.md` for the full threat model.

## Deployment

```bash
# On your VPS
git clone https://github.com/benzac708/pyagent /opt/pyagent
cd /opt/pyagent
cp .env.example .env  # fill in your values
docker compose up -d
curl http://localhost:8000/health  # should return {"status":"ok"}
```

For the watcher:
```bash
cp deploy/watch-checks.example.json /opt/pyagent/watch-checks.json
# edit watch-checks.json with your checks
python3 deploy/vps-agent-watch.py  # test manually
```

## Uninstall

```bash
bash deploy/uninstall.sh [--keep-data] [--dry-run]
```

Removes systemd units, Docker container/image, and app directory. See `deploy/uninstall.sh` for details.

## Contributing

PRs welcome. Run `uv run pytest && uv run ruff check . && uv run mypy agent/ tools/ api/` before submitting.

## License

MIT
EOF
echo "README written"