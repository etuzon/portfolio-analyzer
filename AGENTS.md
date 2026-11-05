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

## Project Chat Shortcuts

- Use `$cad` to invoke the commit-and-deploy skill, or `/prompts:cad` for the legacy custom prompt after reloading Codex. Optional text provides a commit message or release scope. Repository instructions do not register a bare `/cad` command in the slash menu.
- Use the `cad` skill when available. Run `./scripts/commit-and-deploy.sh "<commit message>" <explicit task-owned file>...` from the repository root; the script runs tests, commits the selected files, rebuilds Docker Compose, and checks HTTPS health.
- Preserve unrelated edits and exclude them from both the commit and deployment build. Keep secrets and runtime data out of the commit.
- Complete the script's validation gates, verify the deployed task behavior, and report the commit hash and deployment result. Do not push or merge unless separately requested.
- Explicitly invoking the commit-and-deploy shortcut authorizes this project's established local deployment without another confirmation. A request to create, explain, or edit the shortcut does not invoke a release.

## Safety and Data Rules

- Do not commit or expose secrets from `config.yaml`.
- Do not log passwords, API keys, tokens, connection strings, or provider credentials.
- Treat `data/` as runtime state; avoid editing cached or generated data unless the task explicitly requires it.
- Local portfolio edits must remain local and must not write back to any external import source.

## Frontend Notes

- Keep the first screen as the actual dashboard, not a landing page.
- Preserve the hierarchical sidebar navigation unless explicitly asked to change it.
- Keep interface copy concise and useful. Omit decorative labels and eyebrow text that repeat a nearby heading or add no information needed for a decision or action; for example, do not put "Matches" / "התאמות" above "Active signals". Preserve meaningful field labels, instructions, statuses, and accessibility names.
- User-facing dates in forms, tables, tooltips, and reports should use `dd/mm/yyyy`.
- Loading behavior may be blocking only when explicitly requested; otherwise keep analytics loading lightweight and non-blocking.
- Honor the active interface language completely. Keep API status values machine-readable, but localize every user-visible status, action, count label, error summary, badge, tooltip, and empty state. Hebrew UI must not show English operational labels, and English UI must not show Hebrew labels.
- Every added, changed, or removed functionality must update the affected in-app Help in `web/index.html` and Hebrew translations in `web/i18n.js` in the same task, before completion or release. Verify navigation, prerequisites, units, usage steps, results, permissions, and relevant loading/cache/error/retry behavior against the implementation. Audit all Help sections and navigation/settings coverage when asked for a full Help review; cosmetic-only changes require an accuracy check without filler text.
- For form and table fields, especially numeric amount/percent/age/factor inputs, use stable min-widths or fixed column widths so entered values are visible and not clipped.

## Implementation Notes

### Agent Team and Financial Ownership

- Role and financial skills are versioned in `.agents/skills/`. Keep local user-level skill aliases pointed at these maintained copies rather than editing a second divergent copy.
- Use `principal-engineering-triad` to coordinate applicable UX, development, financial, and independent QA phases. The main agent owns scope and handoffs; the development phase may remain with the main agent or have a dedicated owner.
- For financial calculations, quote/FX normalization, scores, forecasts, portfolio risk, or investment conclusions, use `principal-financial-analyst` and assign a dedicated financial subagent when delegation is available and permitted. This instruction requests that delegation. Load its relevant domain skills on demand; each financial topic does not need its own agent.
- The financial agent owns macro/microeconomic assumptions, company-report evidence, announcements, valuation, instrument conventions, scenario methods, and financial interpretation. Establish source cutoffs, units, formulas, missing-data behavior, scope, and raw numerical examples before implementation; re-check material outputs afterward. Maintained repository models below govern the implemented formulas.
- Agents may ask each other directly for missing evidence and contracts, while recording consequential decisions with the coordinator. Ask the user only for material unresolved product choices, necessary personal suitability facts, or genuinely missing authorization; continue independent work while waiting.
- Keep final QA independent for features and functional fixes under the triad. QA derives financial expectations from requirements and raw evidence; neither developer conclusions nor financial sign-off replace its review. Route financial-method defects to finance, implementation defects to development, and interaction defects to UX, then re-test.
- Schedule role handoffs within available agent slots. Research-only questions need no software lifecycle; cosmetic-only edits need no financial agent. If delegation is unavailable, report same-agent review and any unmet independence requirement. Skill changes configure agent behavior; they do not install data feeds, enable broker execution, or authorize deployment.

### Existing Models and Implementation Patterns

- For financial score, report normalization, or forecast evaluation changes, read [.agents/skills/company-outlook-model/SKILL.md](.agents/skills/company-outlook-model/SKILL.md) and keep its implemented formula aligned with code.
- For portfolio risk, cash-buffer, or borrowing-score changes, read [.agents/skills/trade-simulation/references/portfolio-risk.md](.agents/skills/trade-simulation/references/portfolio-risk.md) and keep the dashboard and simulator on the same model.
- Prefer existing patterns in `app/local_portfolio.py`, `app/main.py`, and `web/app.js`.
- Use provider/cache abstractions already present in `app/providers.py`.
- Keep changes scoped; the worktree may contain unrelated user edits.
- For narrow UI changes, verify with pytest when possible and inspect the affected static files for stale selectors or IDs.
