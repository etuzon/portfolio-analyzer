# Portfolio Analyzer

Dockerized HTTPS dashboard for analyzing a local portfolio database with fundamentals, dividends, price ranges, support/resistance, moving averages, volumes, screeners, FX display, and daily alerts. An external portfolio system can be used as an optional import source; after import, the app reads and analyzes its own local data.

## Run

```bash
cp config.example.yaml config.yaml
docker compose up --build
```

Open `https://localhost:6443`. The container generates a local self-signed certificate if `./certs/server.crt` and `./certs/server.key` do not exist.

Keep `config.yaml` private because it may include external provider credentials or optional import credentials.

## Reset an Admin Password

If an Admin forgets their password, set a temporary replacement from an interactive shell inside the running container:

```bash
docker compose exec portfolio-analyzer python -m app.admin_cli reset-password --username admin
```

The command prompts for the password without putting it in shell history or process arguments. It only resets an existing Admin user, revokes that user's active sessions, and requires another password change at the next dashboard sign-in.

If the service is stopped, run the same recovery command in a temporary container:

```bash
docker compose run --rm portfolio-analyzer python -m app.admin_cli reset-password --username admin
```

## REST API and MCP Access

REST API and MCP access are both off by default. An Admin can open **Settings → REST API & MCP** and independently set each service to:

- **Off**: token creation and bearer-token access are disabled. Saving this mode revokes only that service's active tokens.
- **Read only**: REST tokens can use read endpoints and analysis operations; MCP tokens can call read tools.
- **Read and write**: Admin and Operator tokens may change local data through that service. Viewer tokens always remain read-only.

After the required service is enabled, exchange a dashboard username and password for an eight-hour, service-specific token. Omit `service` for backward-compatible REST behavior:

```bash
curl --insecure https://localhost:6443/api/auth/token \
  --header 'Content-Type: application/json' \
  --data '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD","service":"rest"}'
```

Use the returned `access_token` without a CSRF header:

```bash
curl --insecure https://localhost:6443/api/local/reports \
  --header 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

For MCP, request a token with `"service":"mcp"`, then configure the client with:

- URL: `https://localhost:6443/mcp/`
- Transport: Streamable HTTP
- Header: `Authorization: Bearer YOUR_MCP_ACCESS_TOKEN`

Read tools expose access status, accounts, filtered reports, and account trends. When MCP is in **Read and write** mode, Admin and Operator tokens can also record local transactions and save historical prices. Write tools never write back to an external import source.

`DELETE /api/auth/token` revokes the bearer token used for that request, including an MCP token when REST is off. Tokens are stored only as SHA-256 hashes and are also revoked when the user is disabled, changes their password, or an Admin turns the relevant service off. Users with a temporary password must complete the dashboard password-change flow before creating a token.

## Read-only LLM assistant

Type in the chat box above the dashboard to open the assistant. Chats are private to the signed-in application user and survive reloads. Use **New chat** to start a separate conversation. **Settings → Portfolio assistant** controls the number retained (default `10`, range `1–100`). Creating a chat or lowering the limit removes conversations with the oldest last message; opening a conversation does not make it newer. Failed questions keep the draft and do not replace prior messages. Existing single-conversation context migrates once.

The default provider is the locally signed-in **Codex CLI**, so no API key is required. On the host, run:

```bash
codex login
./scripts/start-codex-bridge.sh
docker compose up --build -d
```

Codex must be signed in as the OS user starting the bridge. The release script starts the bridge when it finds a signed-in CLI. Restart the bridge after a host reboot. `PORTFOLIO_CODEX_DIR` changes its default socket directory `/tmp/portfolio-codex` for both the starter and Compose. For a local Uvicorn process, set `PORTFOLIO_CODEX_SOCKET=/tmp/portfolio-codex/bridge.sock`. If an older private config explicitly disables `llm`, set `provider: local_codex` and `enabled: true`, or use `PORTFOLIO_ASSISTANT_PROVIDER=local_codex`. Unavailable Codex sign-in, plan limits or bridge failures leave saved chats readable and return a recoverable send error.

The bridge exposes only a local Unix socket. It receives conversation evidence and tool descriptions, with no application authentication headers or database connection configuration. Each model exchange is an ephemeral, structured-output Codex app-server turn with native tools, hooks, user MCP servers, connectors, shell, images, browser, skills and child agents disabled before startup. A restricted permission profile denies filesystem access outside minimal runtime files and an empty temporary workspace, and denies command network access. Temporary model state is removed after the response. The CLI manages its existing authentication; credentials are never copied into Docker. The model selects a named read or returns an answer; it cannot execute tools itself.

The application validates that selection against the code-owned catalog at `GET /api/assistant/read-tools`, then makes an authenticated **GET** through the actual FastAPI REST routes using the requesting user's identity. Unknown tools/arguments, arbitrary URLs, path traversal, redirects and all write verbs are rejected. The agent has no database interface. Approved routes cover accounts, current holdings, transactions and trade history, reports, historical prices, fundamentals, dividends, quote/provider status, market screening, pensions, FX, events and alerts. The popup displays the allowlist. Chat/settings persistence is application-owned and is never exposed as an agent capability.

Each question permits at most **six model exchanges including its final answer**, with at most one approved read per exchange. The last exchange has no tools. The next user message gets a new budget. Only the last `llm.max_context_messages` user/assistant messages (default `12`; `0` disables context) are passed as conversation context, while the complete saved conversation remains visible. Prompts require evidence, unknown-data disclosure, per-currency amounts, `dd/mm/yyyy` dates, and answers in the active language. These instructions reduce guessing; independent simulations are still needed to evaluate real answers.

An API-key provider remains optional: set `llm.provider: openai`, `enabled: true`, `base_url`, `api_key` and `model` in private `config.yaml`. It uses `POST /chat/completions`; credentials remain server-side. `llm.reasoning_effort` is forwarded to that provider. Model/provider compatibility must be configured explicitly.

The controlled 30-conversation, three-question regression corpus is in `tests/test_assistant_qa_simulations.py`. To replay it against the real local Codex model using only synthetic portfolio/provider data, start the bridge and run:

```bash
PORTFOLIO_CODEX_SOCKET=/tmp/portfolio-codex/bridge.sock ./.venv/bin/python tests/assistant_real_replay.py
```

Transcripts and review flags are saved under `/tmp/portfolio-chat-qa`. The real replay is opt-in and is not run by pytest. Synthetic provider facts and real model behavior are reported separately; automated flags do not establish answer correctness.

## World-event research workflow

Curated historical examples are bundled under `app/workflows/cases/` and exposed
through `get_event_impact_cases` or authenticated
`GET /api/assistant/workflows/world-event-impact/cases?symbol=BBD`.
The Brazil election example includes BBD and eight comparison stocks, with
aligned USD closing returns, EWZ/SPY context and filing-backed exposure channels.
Pass `event_id=brazil-presidential-runoff-2026-10-25` to retrieve the full group.
Details are paginated (default and maximum `limit=5`); continue with `next_offset`
until it is null. `count` is the page size and `total_count` is the filtered total.
Use `get_event_impact_events` or authenticated
`GET /api/assistant/workflows/world-event-impact/events` for the compact inventory.
The library now also covers eight historical event groups: pandemic disruption,
vaccine reopening, Brexit, Japan's earthquake/nuclear crisis, Saudi oil-facility
attacks, Russia's invasion and sanctions, US banking stress, and AI-efficiency
repricing. See the [historical event inventory](research/world-events/historical-event-library.md)
for sessions, observed percentages and sources. Related episodes share an event
family; they are not assumed independent.
Responses include related `event_patterns` from `app/workflows/patterns/`:
reason → business exposure → transmission → possible effect, with offsets and
missing estimates. `distinct_event_count` counts event IDs, not independent
statistical trials. These manually maintained records are readable examples;
they do not establish a calibrated loss probability. See the
[sourced comparison](research/world-events/brazil-2026-10-26.md).

The assistant can load `get_event_impact_workflow`, also available at authenticated
`GET /api/assistant/workflows/world-event-impact`. Its canonical template is
[`app/workflows/world-event-impact.yaml`](app/workflows/world-event-impact.yaml),
with a repository skill at [`.agents/skills/world-event-impact/SKILL.md`](.agents/skills/world-event-impact/SKILL.md).
Ask the assistant to use the world-event workflow, then supply stocks, dates and
observed moves. It separates sourced facts, possible explanations, historical
observations and validated forecasts, including different effects across regions.

Records cover event occurrence, company exposure, direction, severity, impact
onset, persistence, recovery, spillover, scenario branches and joint portfolio
loss. Stock returns, revenue and net income have separate baselines and horizons.
Unsupported percentages remain unknown. Historical frequencies require a defined
comparison population; selected winners/losers alone cannot establish predictive
probabilities. Validation includes uncertainty, dependence and chronological
holdout checks; the interval method references the
[NIST statistical handbook](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

This release supplies a workflow, blank records and a versioned read-only case
library. It does not provide automated news ingestion, assistant case-writing,
a probability calculator or a trained learning model.
The read-only assistant cannot save research cases through this tool. Its limited
chat context is not durable learning. Later implementation can consume these
versioned records without treating unverified examples as established outcomes.

## Data Sources

The dashboard reads holdings, transactions, account records, pension/fund records, and manual prices from the local SQLite portfolio database. External portfolio data is imported only when the Sync import action is run. Dividends, income, company profit, market cap, long price history, profile data, and non-portfolio stock screening come from configured market-data APIs:

- Alpha Vantage: adjusted daily prices, dividends in adjusted time series, income statements, overview, and FX.
- Financial Modeling Prep: historical prices, statements, profiles, dividends, symbol search, and screeners.

Set `ALPHA_VANTAGE_API_KEY` or `FMP_API_KEY` before `docker compose up -d --build`. Yahoo and Google Finance are intentionally disabled by default: Yahoo is unofficial/rate-limited, and Google Finance is a Sheets function rather than a supported backend API.

Market API responses are cached in `data/market-cache.sqlite3`. Configure the cache cap with `market_data.max_cache_mb`; the default is `300`.

The top banner is configured with `dashboard.banner_items`. Currency pairs use the no-key Frankfurter FX adapter by default; indexes, gold, and other quote symbols use the configured quote provider when available.

The Market Screener window searches stocks outside the portfolio through Financial Modeling Prep when `FMP_API_KEY` is set.
