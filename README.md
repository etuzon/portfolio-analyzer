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

The optional in-app assistant uses an OpenAI-compatible `POST /chat/completions` provider and can answer in the language of the question. Configure the `llm` section in private `config.yaml`; leave `enabled: false` until a provider URL, API key, and model are set. The key remains server-side and is never included in API responses or prompts.

Set `llm.model` to the model identifier supported by your provider and `llm.reasoning_effort` to one of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, or `max`. The effort setting is forwarded as `reasoning_effort` in the provider request; choose a provider/model that supports it.

The app saves each signed-in user's prompts and final answers locally as limited conversation context (`llm.max_context_messages`, default `12`). Tool payloads are not retained as context. `POST /api/assistant/context/clear` removes that user's saved context, so the next question starts a new conversation.

For each question, the model receives only a fixed catalog at `GET /api/assistant/read-tools`. It can request application-owned read skills for portfolio/risk, accounts, securities, price history and technicals, funds, events, alerts, FX, market data, reports, and screeners. Read data uses `GET`; bounded read calculations use a catalogued `POST` endpoint with a JSON body. It cannot choose arbitrary REST paths and cannot invoke a write endpoint. `POST /api/assistant/questions` runs the model/tool exchange and enforces `llm.max_tool_loops` (default `6`) for that one user prompt; the next prompt starts a new bounded exchange.

## Data Sources

The dashboard reads holdings, transactions, account records, pension/fund records, and manual prices from the local SQLite portfolio database. External portfolio data is imported only when the Sync import action is run. Dividends, income, company profit, market cap, long price history, profile data, and non-portfolio stock screening come from configured market-data APIs:

- Alpha Vantage: adjusted daily prices, dividends in adjusted time series, income statements, overview, and FX.
- Financial Modeling Prep: historical prices, statements, profiles, dividends, symbol search, and screeners.

Set `ALPHA_VANTAGE_API_KEY` or `FMP_API_KEY` before `docker compose up -d --build`. Yahoo and Google Finance are intentionally disabled by default: Yahoo is unofficial/rate-limited, and Google Finance is a Sheets function rather than a supported backend API.

Market API responses are cached in `data/market-cache.sqlite3`. Configure the cache cap with `market_data.max_cache_mb`; the default is `300`.

The top banner is configured with `dashboard.banner_items`. Currency pairs use the no-key Frankfurter FX adapter by default; indexes, gold, and other quote symbols use the configured quote provider when available.

The Market Screener window searches stocks outside the portfolio through Financial Modeling Prep when `FMP_API_KEY` is set.
