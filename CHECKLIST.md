# pyagent — Build Checklist

Cross off each step as you complete it. Each version is one git commit.

---

## v1: Core LLM call

- [x] Create repo + `git init`
- [x] Install `uv`, create venv
- [x] Create `pyproject.toml` with deps + ruff + pytest config
- [x] Create `.env.example` and `.gitignore`
- [x] Write `agent/config.py` (load .env, validate required vars)
- [x] Write `agent/loop.py` (single LLM call, print response)
- [x] `uv run python -m agent "hello"` works (structure verified, needs API key)
- [x] Commit: `v1: core LLM call with OpenAI-compatible API`

## v2: Tool registry + read_file

- [x] Create `tools/registry.py` (list of tool dicts)
- [x] Create `tools/read_file.py` (read file, return string, catch errors)
- [x] Register read_file in registry
- [x] Update agent loop to handle `tool_calls`
- [x] `uv run python -m agent "read fizzbuzz.js"` calls tool + summarizes (needs API key)
- [x] Commit: `v2: tool registry with read_file`

## v3: Multiple tools + safety

- [x] Create `tools/list_files.py`
- [x] Create `tools/bash.py` (with timeout)
- [x] Create `tools/edit_file.py` (write-to-temp-then-rename)
- [x] Add max iterations (10) to loop
- [x] Tools return error strings, not exceptions
- [x] `uv run python -m agent "list .py files and read first one"` works
- [x] Test: agent stops at 10 iterations on bad input
- [x] Commit: `v3: multiple tools, max iterations, safety guards`

## v4: Provider switching

- [x] Test with OpenAI (change .env)
- [x] Test with Ollama (change .env)
- [x] Document tested providers in README
- [x] Commit: `v4: verified with multiple providers`

## v5: SQLite state

- [x] Create `agent/db.py` (init, save message, save run)
- [x] Store full conversation thread
- [x] Store run metadata (iterations, tokens, status, error)
- [x] Agent resumes conversation after restart
- [x] `sqlite3 agent.db "SELECT * FROM runs"` shows data
- [x] Commit: `v5: SQLite state + run traces`

## v6: Observability

- [x] Add structlog (JSON output)
- [x] Track tokens per run in DB
- [x] Create `api/server.py` (FastAPI with /health)
- [x] `/health` returns `{"status": "ok"}`
- [x] Commit: `v6: structured logging, cost tracking, health endpoint`

## v7: Deployment

- [x] Write `Dockerfile`
- [x] `docker build` succeeds (verified on VPS)
- [x] `docker run` works locally (container runs, health ok)
- [x] Write `deploy/agent.service` + `deploy/agent.timer`
- [x] Deploy to VPS, `systemctl is-active` confirms running
- [x] Caddy serves HTTPS (https://pyagent.zachara.dev)
- [x] Commit: `v7: Docker + systemd + Caddy deployment`

## v8: Polish

- [x] Write `tests/test_tools.py` (test each tool)
- [x] Write `tests/test_config.py`
- [x] `uv run pytest` passes
- [x] Create `.github/workflows/ci.yml`
- [x] GitHub Actions green
- [x] README with architecture diagram + "why" sections
- [x] Commit: `v8: tests, CI, documentation`

---

## ISA Claims (map to versions)

| Claim | Version | Status |
|-------|---------|--------|
| ISC-1 | v1 | ✅ |
| ISC-2 | v2 | ✅ |
| ISC-3 | v3 | ✅ |
| ISC-4 | v4 | ✅ |
| ISC-5 | v5 | ✅ |
| ISC-6 | v6 | ✅ |
| ISC-7 | v7 | ✅ |
| ISC-8 | v8 | ✅ |
| ISC-9 | v8 | ✅ |
| ISC-10 | v8 | ✅ |

---

## Notes

- Each version = one git commit. Git log tells the story.
- Verify before moving on. Don't skip verification steps.
- Stop anytime. Every version is a working, deployable thing.
- v3 alone is a useful agent. Everything after is polish.
