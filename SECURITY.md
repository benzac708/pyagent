# Security

## Threat Model

The agent can read files, check disk/backup health, and query its own run history. It cannot run arbitrary shell commands, edit files, or access secrets - these capabilities are not registered as tools.

## Permission Tiers

| Tier | Tools | Approval |
|---|---|---|
| Read-only | `read_file`, `list_files`, `check_disk`, `check_backups`, `check_health`, `list_runs` | None |
| Mutating | `bash`, `edit_file` | Allowlisted in production via `ALLOWED_TOOLS` |
| Destructive | None registered | N/A |

## Sandbox Isolation

- Agent runs inside a Docker container as a non-root user.
- Secrets are injected via `EnvironmentFile`, not baked into the image.
- `.env` is gitignored and never committed.

## Cost / Iteration Caps

- `MAX_ITERATIONS` (default 10) - hard stop on the agent loop.
- `MAX_TOKENS` (default 50000) - hard stop on total tokens per run.
- `MAX_OUTPUT_RETRIES` (default 2) - bounds JSON correction retries.
- Watcher uses tighter caps: 5 iterations, 8000 tokens.

## Audit Logging

- Every tool call, LLM response, and run result is logged via structlog (JSON).
- Secret values are redacted in logs (`[REDACTED]`).
- The watcher maintains an append-only audit log at `/opt/vps-ops/pyagent-actions.log`.

## Human-in-the-Loop Gates

- Tier 2+ actions (config edits, scaling, credential rotation) require human approval.
- The agent recommends; the watcher or human executes.

## Prompt-Injection Defenses

- Tool inputs are validated against Pydantic schemas.
- Tool outputs are treated as untrusted data.
- `read_file` has a path denylist for sensitive files.
- `ALLOWED_TOOLS` filters the registry at import time - the model cannot call tools that don't exist.
EOF
echo "SECURITY.md written"