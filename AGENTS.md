# Agent Instructions

## Project Overview

This repository contains a Dockerized portfolio analysis dashboard.

- Backend: FastAPI application in `app/`.
- Frontend: static HTML/CSS/JavaScript in `web/`.
- Tests: pytest suite in `tests/`.
- Runtime config: `config.yaml`, based on `config.example.yaml`.
- Runtime data: `data/`, including SQLite databases and market-data caches.

## Development Commands

Run the test suite with:

```bash
./.venv/bin/python -m pytest
```

Run the app locally with:

```bash
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If `data/` is not writable in the local workspace, use a temporary writable data directory:

```bash
mkdir -p /tmp/portfolio-analyzer-data
DATA_DIR=/tmp/portfolio-analyzer-data ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Docker usage:

```bash
docker compose up --build
```

The Docker app is served at `https://localhost:6443`.

## Safety and Data Rules

- Do not commit or expose secrets from `config.yaml`.
- Do not log passwords, API keys, tokens, connection strings, or provider credentials.
- Treat `data/` as runtime state; avoid editing cached or generated data unless the task explicitly requires it.
- Local portfolio edits must remain local and must not write back to any external import source.

## Frontend Notes

- Keep the first screen as the actual dashboard, not a landing page.
- Preserve the hierarchical sidebar navigation unless explicitly asked to change it.
- User-facing dates in forms, tables, tooltips, and reports should use `dd/mm/yyyy`.
- Loading behavior may be blocking only when explicitly requested; otherwise keep analytics loading lightweight and non-blocking.
- Honor the active interface language completely. Keep API status values machine-readable, but localize every user-visible status, action, count label, error summary, badge, tooltip, and empty state. Hebrew UI must not show English operational labels, and English UI must not show Hebrew labels.
- For form and table fields, especially numeric amount/percent/age/factor inputs, use stable min-widths or fixed column widths so entered values are visible and not clipped.

## Implementation Notes

- Prefer existing patterns in `app/local_portfolio.py`, `app/main.py`, and `web/app.js`.
- Use provider/cache abstractions already present in `app/providers.py`.
- Keep changes scoped; the worktree may contain unrelated user edits.
- For narrow UI changes, verify with pytest when possible and inspect the affected static files for stale selectors or IDs.
