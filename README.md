# Portfolio Analyzer

Dockerized HTTPS dashboard for analyzing a local portfolio database with fundamentals, dividends, price ranges, support/resistance, moving averages, volumes, screeners, FX display, and daily alerts. An external portfolio system can be used as an optional import source; after import, the app reads and analyzes its own local data.

## Run

```bash
cp config.example.yaml config.yaml
docker compose up --build
```

Open `https://localhost:6443`. The container generates a local self-signed certificate if `./certs/server.crt` and `./certs/server.key` do not exist.

Keep `config.yaml` private because it may include external provider credentials or optional import credentials.

## Trade planning and signals

**Securities → Account recommendation** accepts a stock, Buy or Short, and an optional amount/currency. Buy-signal cards offer the same planner directly. Suggestions use current ledger cash, recent dated prices, the existing account-risk model, cash reserves, stock/sector concentration, and retirement-horizon and volatility proxies. US listings require US investment accounts with USD cash. Missing prices, FX, or unverifiable cash produce an explanation instead of an amount. Saved local instruments can be planned before they are held. Planning never records a transaction or changes the portfolio.

Sizing defaults and the limiting factor appear with each result. Short suggestions are conditional estimates: the model reserves twice the short exposure from existing cash, and broker permissions, borrow availability, and actual margin requirements remain unverified. Separate suggestions reuse the same cash and must not be added together as a spending plan.

Use **Dismiss** on an active signal to hide the same stock and signal type across all rules, including later runs. **Settings → Portfolio signals** controls the period (default **60 days**, range **1–3650**). Settings and dismissals persist in `data/alerts.json`. Changing the period affects new dismissals; existing expiry dates remain unchanged. Admins and Operators can dismiss signals and save the period; Viewers can read the setting.

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

## Dashboard account values

Account risk cards show each account's share of the full primary portfolio's net account value (holdings plus signed cash), converted to the dashboard base currency. Holdings filters do not change those shares. Separately managed employee equity is excluded from this primary portfolio scope. A missing conversion or a nonpositive total shows an unavailable value.

Security tooltips distinguish the exchange from the data provider. Saved profile exchange metadata remains available during initial loading and refresh without changing stored holding identities.

## Read-only LLM assistant

Type in the chat box in the main menu to open the assistant. Chats are private to the signed-in application user and survive reloads. Use **New chat** to start a separate conversation. **Settings → Portfolio assistant** controls the number retained (default `10`, range `1–100`). Creating a chat or lowering the limit removes conversations with the oldest last message; opening a conversation does not make it newer. Failed questions keep the draft and do not replace prior messages. Existing single-conversation context migrates once.

Use the delete action beside a conversation and confirm to remove that saved chat. Deleting another conversation preserves the current draft. Chat diagnostics follow the separate logging retention settings.

Assistant answers support headings, lists, emphasis, tables, code blocks, and semantic colors. JSON code blocks are indented without rounding number tokens. Tables scroll within the message on small screens. Rendering escapes raw HTML and does not load model-supplied links, images, styles, or scripts; user messages remain plain text. Oversized formatting falls back to escaped text without dropping content.

The default provider is the locally signed-in **Codex CLI**, so no API key is required. On the host, run:

```bash
codex login
./scripts/start-codex-bridge.sh
docker compose up --build -d
```

Codex must be signed in as the OS user starting the bridge. The release script starts the bridge when it finds a signed-in CLI. The starter uses a systemd user service for each repository/socket path when available: it survives the starting terminal, restarts after crashes and starts at the next user login. On hosts without a user service manager, or with `--no-service`, it starts a detached process that must be started again after a reboot. The default socket directory is the private, Git-ignored `.runtime/portfolio-codex` in this repository, so temporary-directory cleanup cannot delete a running container's bridge mount. `PORTFOLIO_CODEX_DIR` overrides this directory for both the starter and Compose; use the same absolute override when starting both. The starter also reads a literal `PORTFOLIO_CODEX_DIR` from the repository's `.env` without sourcing other settings; export an interpolated directory value explicitly. For local Uvicorn, set `PORTFOLIO_CODEX_SOCKET="$PWD/.runtime/portfolio-codex/bridge.sock"`. If migrating an existing container from `/tmp/portfolio-codex`, recreate it through the normal authorized release process to adopt the new mount. If an older private config explicitly disables `llm`, set `provider: local_codex` and `enabled: true`, or use `PORTFOLIO_ASSISTANT_PROVIDER=local_codex`. Unavailable Codex sign-in, plan limits or bridge failures leave saved chats readable and return a recoverable send error.

The missing-data workflow uses `price_agent.provider`, `model` and `reasoning_effort` (Codex, `gpt-6.1-sol`, medium by default), independently of the chat model in `llm`. The shared host bridge invokes the signed-in CLI for structured planning decisions. The application executes only its authenticated, allowed search/read/follow REST tools, validates fetched public evidence and saves qualified results itself. A successful bridge inference does not establish that public-source retrieval or a portfolio update succeeded. Missing sockets, unreachable bridges, disabled AI and provider/model failures have separate status codes; start or restart the host bridge before retrying a connection failure. Inspect the container's `/run/portfolio-codex` bind source when troubleshooting: a healthy bridge listening in a different host directory is unavailable to that container. Find installed user services with `systemctl --user list-unit-files 'portfolio-codex-bridge-*'`. The bridge's socket-only `GET /health` checks the bridge process, not model sign-in or source retrieval.

Discovery may use exact CUSIPs, their printed six-plus-three format, alternative U.S. ISIN search spellings and maintained source hints; these are leads, never verified identifiers or coverage claims. Recognized U.S. bond candidates may receive a Public exact-CUSIP page hint; only an actual matching primary instrument heading can qualify a name. The current TVA catalog points checksum-valid `88059E` bond identifiers to the issuer's [2000 Series G offering document](https://s205.q4cdn.com/318912997/files/doc_downloads/irw/tva_bonds/2000-g.pdf), which covers only a subset of components. Saving an issuer name requires a fresh read with the literal issuer title, the explicit component section, and the exact checked ISIN and printed CUSIP on the same row. The adapter saves only the issuer name; it never assigns the parent bond's coupon or maturity to a STRIP, invents a current quote, closes a holding or credits redemption cash. Names such as `US_<CUSIP>` are generated identifier placeholders and may be replaced by verified names; custom names remain protected.

The bridge exposes only a local Unix socket. It receives conversation evidence and tool descriptions, with no application authentication headers or database connection configuration. Each model exchange is an ephemeral, structured-output Codex app-server turn with native tools, hooks, user MCP servers, connectors, shell, images, browser, skills and child agents disabled before startup. A restricted permission profile denies filesystem access outside minimal runtime files and an empty temporary workspace, and denies command network access. Temporary model state is removed after the response. The CLI manages its existing authentication; credentials are never copied into Docker. The model selects a named read or returns an answer; it cannot execute tools itself.

The application validates that selection against the code-owned catalog at `GET /api/assistant/read-tools`, then makes an authenticated **GET** through the actual FastAPI REST routes using the requesting user's identity. Unknown tools/arguments, arbitrary URLs, path traversal, redirects and all write verbs are rejected. The agent has no database interface. Approved routes cover accounts, current holdings, transactions and trade history, reports, historical prices, fundamentals, dividends, quote/provider status, market screening, pensions, FX, events and alerts. The catalog is enforced internally rather than displayed in the chat popup. Chat/settings persistence and user-initiated conversation deletion are application-owned and are never exposed as agent capabilities.

Each question permits at most **five model exchanges including its final answer**, and at most five REST attempts including failures, with at most one approved read per exchange. The last exchange has no tools. The next user message gets a new budget. Only the last `llm.max_context_messages` user/assistant messages (default `12`; `0` disables context) are passed as conversation context, while the complete saved conversation remains visible. Prompts require evidence, unknown-data disclosure, per-currency amounts, `dd/mm/yyyy` dates, and answers in the active language. These instructions reduce guessing; independent simulations are still needed to evaluate real answers.

An API-key provider remains optional: set `llm.provider: openai`, `enabled: true`, `base_url`, `api_key` and `model` in private `config.yaml`. It uses `POST /chat/completions`; credentials remain server-side. `llm.reasoning_effort` is forwarded to the selected provider, including local CLIs. Set `llm.provider: local_claude` (or `claude`) for Claude Code; the existing socket bridge supports both CLIs. Start it with `./scripts/start-codex-bridge.sh --restart` after installing/signing in to the chosen CLI. The price updater uses its own `price_agent` settings and never gives dashboard chat write tools. Model/provider compatibility must be configured explicitly.

The controlled 30-conversation, three-question regression corpus is in `tests/test_assistant_qa_simulations.py`. To replay it against the real local Codex model using only synthetic portfolio/provider data, start the bridge and run:

```bash
PORTFOLIO_CODEX_SOCKET="$PWD/.runtime/portfolio-codex/bridge.sock" ./.venv/bin/python tests/assistant_real_replay.py
```

Transcripts and review flags are saved under `/tmp/portfolio-chat-qa`. The real replay is opt-in and is not run by pytest. Synthetic provider facts and real model behavior are reported separately; automated flags do not establish answer correctness.

For missing-data research, `./.venv/bin/python tests/security_research_real_replay.py --main tase` runs the actual application login, password change, authenticated research tools, live model, public-source reads, validation and saving against a temporary synthetic portfolio. Replace `tase` with `bond` or `tva` for the bond cases, or `mixed` for the original three-candidate request with the third bond retained on its API route. It uses the stable host bridge by default, or `PORTFOLIO_CODEX_SOCKET` when set, and never loads private configuration or the runtime portfolio. The output distinguishes verified saved facts from remaining gaps and includes source dates, raw units, request counts and before/after ledger values. These opt-in live checks consume model and Internet calls; ordinary pytest remains offline.

### Company credit ratings

The Holdings table shows saved Moody’s, S&P Global Ratings and Fitch summaries
beside each security. Loading the table reads the cache in the background and
does not start provider or AI research. Repeated positions in one security share
the same exact symbol/market/currency summary. Open a row’s rating details,
**Portfolio → Securities → Ratings**, or the security overview for complete
scope, original dates and sources. **Refresh ratings** requires Admin or Operator permission, checks
configured APIs first and uses the existing bounded AI Internet workflow for
missing information. The eight-model, eight-REST and eight-web limits are shared
across the request; the model has no database, filesystem or direct-write tools.
API-priced stocks remain eligible for this separate ratings check.

The licensed adapter uses [S&P Global Agency Ratings](https://xpressapi.marketplace.spglobal.com/swagger/?urls.primaryName=agencyratings),
which covers all three agencies' issuer and issue ratings. Merge into private
`config.yaml`:

```yaml
market_data:
  credit_ratings:
    verification_ttl_days: 30
    spglobal:
      enabled: true
      bearer_token: "${SPGLOBAL_RATINGS_TOKEN}"
```

Docker Compose forwards `SPGLOBAL_RATINGS_TOKEN` from the host or private `.env`;
recreate the container after changing it. Suitable ratings entitlements are
required. Public-source AI research can run without this token using the
configured signed-in CLI and public reader/search services.

`GET /api/securities/credit-ratings?symbol=JPM&stock_market=NYSE&currency=USD`
is cache-only. The table uses `GET /api/securities/credit-ratings/summaries` with
up to 200 repeated `security_keys` query values. Its `summary_only` responses
preserve financial categories and freshness but omit long evidence excerpts;
the single-security overview retains those excerpts. `POST /api/securities/credit-ratings/ai` accepts up to three
`security_keys` and `position_scope`; poll the returned request at
`GET /api/securities/credit-ratings/ai/{request_id}`. Viewer access is read-only.
Facts persist in the application cache, with original source excerpts and
separate rating, observation, retrieval and forward-signal dates. An unsuccessful
refresh retains verified facts and records the attempt. A different security
cannot attach to another running request.

Issuer, exact issue, deposit, senior-unsecured class, short-term and national-scale
ratings remain distinct. A verified debt-class rating appears in **Other rating
categories** when no primary issuer rating is available; its own outlook and
source dates remain visible. Missing evidence does not mean Unrated or Stable.
Portfolio risk calculations remain unchanged pending the separate risk review.

### Security price API and AI updater

#### Automatic U.S. bond and fund retrieval

`GET /api/security/market-data` retrieves provider data automatically. Supply an
identifier and instrument kind, not manually entered prices. It works for
supported U.S. bonds, mutual funds and ETFs generally; no sample CUSIP is
hardcoded and the security need not already be registered or held.

```text
/api/security/market-data?identifier=91282CKD2&kind=bond
/api/security/market-data?identifier=037833DV9&kind=bond&identifier_type=cusip
/api/security/market-data?identifier=SWPPX&kind=fund&date_from=01/01/2025&date_to=31/12/2025
/api/security/market-data?identifier=VTI&kind=etf
```

Parameters:

| Parameter | Meaning |
| --- | --- |
| `identifier`, `kind` | Exact identifier and `bond`, `fund` or `etf` |
| `identifier_type` | `auto`, `cusip`, `isin` or `ticker`; bonds require CUSIP/ISIN |
| `provider` | `auto`, `finnhub`, `eodhd` or `treasury_direct` |
| `date_from`, `date_to` | Inclusive `dd/mm/yyyy` or ISO dates; defaults to the last 31 days through today |
| `refresh` | Retry the provider even when a fresh cache entry exists |
| `cache_only` | Read retained evidence without provider access; incompatible with `refresh` |

The response contains confirmed `security` identity, dated `items`,
`latest_in_range`, `quote`, reference `details`, coverage, source URLs, retrieval
time and provider/cache statuses. A historical query has `quote: null` so its
last historical observation is not labelled current. A current-range quote is
the last available observation, not a guaranteed live executable price.
`details_scope` explicitly marks the profile as the latest provider data rather
than historical holdings, ratings or other point-in-time reference data.

Configure `market_data.security_lookup` in the existing private `config.yaml`:

```yaml
market_data:
  security_lookup:
    cache_ttl_hours: 24
    max_provider_requests: 5
    treasury_direct:
      enabled: true
    finnhub:
      enabled: true
      api_key: "${FINNHUB_API_KEY}"
    eodhd:
      enabled: true
      api_key: "${EODHD_API_KEY}"
```

Merge this subsection with the existing market-data configuration. Provider keys
stay server-side. Docker Compose forwards `FINNHUB_API_KEY`, `EODHD_API_KEY`
and `BRAVE_SEARCH_API_KEY` from the host environment or private `.env` file;
recreate the container after changing them. Finnhub bond profiles/history require suitable entitlements;
EODHD fund/ETF reference data and history depend on account access and coverage.
The public TreasuryDirect fallback is for Treasury securities, not corporate
bonds. Its daily files require separate bounded requests, so returned history
can be partial; inspect `coverage.next_date` and `truncated`. Do not loop over a
long history without considering the remaining request budget. Each fetch has a
hard maximum of five upstream attempts, including failures and redirects; it
does not invoke an LLM. Existing AI requests retain their independent five-model
and five-application-REST ceilings. No subscription is purchased by this code.

Saved snapshots reuse `SqliteCache`. Fresh entries avoid provider calls; failed
refreshes preserve useful snapshots marked stale. `not_configured`, `not_found`,
`provider_error`, `partial` and `missing` distinguish configuration, coverage and
availability problems. Missing prices are not fabricated or filled. Source raw
units and bases are retained: percent-of-par is distinct from cents, and a fund
NAV is not automatically an ETF market close. Provider-adjusted close remains
separate from raw close. Treasury programme purchase/redemption columns retain
their provider definitions. Coupon and auction data are not current market yield
or a secondary-market quote.

This endpoint is authenticated and available to Viewer users and authorized
read-only REST clients. It updates only the provider research cache, not local
price overrides, securities, transactions, quantities or cash. Existing bond
holdings do not declare face value per quantity unit; fetched percent-of-par
prices therefore do not automatically revalue positions. The dedicated
`us-bond-fund-data` skill is shared by Codex and Claude Code, and dashboard chat
can call `get_security_market_data` directly. Its research guidance remains open
to other suitable financial sources when the configured providers lack data.

AI agents must never read or write application databases directly or through
SQL, ORMs, local database files or shell helpers. Their entire application-data
boundary is an explicit REST allowlist, authenticated and authorized using the
initiating user's identity. A successful sign-in does not grant write access:
roles, token service/access modes and browser CSRF remain enforced at the actual
routes. Application endpoints own internal persistence; no database connection
or arbitrary URL/SQL tool is exposed to the model.

Provider contracts:
[Finnhub owner SDK](https://github.com/Finnhub-Stock-API/finnhub-python),
[TreasuryDirect daily pricing](https://www.treasurydirect.gov/GA-FI/FedInvest/selectSecurityPriceDate),
[EODHD fund fundamentals](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds),
[EODHD history](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes).

#### Dated local price overrides

`config.yaml` is the existing private configuration file; `config.example.yaml`
contains the documented defaults. The host-side price updater uses a separate
`price_agent` section. Dashboard chat remains read-only.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/api/security/price?symbol=AAPL&stock_market=NASDAQ` | Latest saved observation and its date/status; no live download |
| GET | `/api/security/prices?symbol=AAPL&stock_market=NASDAQ&date_from=01/10/2026&date_to=31/10/2026` | Saved local/cached raw history, listing metadata and current observation |
| PUT | `/api/security/prices` | Atomically upsert dated local observations; one row can update current, a batch can correct history |

The security must already be registered in Securities, including currency,
location, asset class and market. Secondary symbols resolve to its canonical
identity. Dates accept `dd/mm/yyyy` or ISO; API records use ISO. Reads are
non-downloading and history may be incomplete. A historical filter never changes
which saved observation is current. `missing`, `dated` and `stale` are machine
statuses; `dated` does not establish live freshness. Prices older than seven
days are stale. Future and out-of-retention dates are rejected.

PUT body example (replace the synthetic source with the actual evidence URL):

```json
{
  "symbol": "AAPL",
  "stock_market": "NASDAQ",
  "items": [{
    "price_input": 123.45,
    "price_date": "2026-11-06",
    "currency": "USD",
    "quote_unit": "currency",
    "price_basis": "close",
    "source_url": "https://exchange.example/AAPL/history",
    "evidence_quote": "AAPL NASDAQ USD 06 November 2026 Close 123.45",
    "observed_at": null,
    "retrieved_at": "2026-11-07T08:00:00Z"
  }]
}
```

`price_input` is the raw source quote. Match the returned `security.quote_unit`:
Israeli inputs use `agorot` and US bonds use `cents` (both divided by 100);
other supported inputs use `currency`. Bond percent-of-par and adjusted closes
are unsupported. Only positive finite numbers and `last`/`close` bases are
accepted. Retain an actual timezone-aware `observed_at` only when known; date-only
evidence uses null. `retrieved_at` records evidence retrieval, not quote time.
Do not replace a known same-day timestamp with older or undated evidence. Up to
500 unique dates per REST batch commit together. The AI controller caps proposals
at 100. The route validates evidence fields but does not independently fetch or
authenticate a caller's source claims.

All routes use existing authentication. Admins enable REST access in Settings;
reads require an authorized token, and writes require REST **Read and write**
mode with an Admin/Operator token. Browser writes also require CSRF. Writes stay
local and invalidate aggregate portfolio caches while retaining market evidence.
These explicit corrections win same-day provider ties in valuation; later
provider dates supersede them. Current, dashboard and account-history values
therefore retain the saved correction without changing holdings or cash.

Invoke `$security-price-update` in Codex or `/security-price-update` in Claude
Code, or run the controller directly:

```bash
./.venv/bin/python scripts/update-security-prices.py --symbol AAPL --stock-market NASDAQ --dry-run --ca-file certs/server.crt
./.venv/bin/python scripts/update-security-prices.py --symbol AAPL --stock-market NASDAQ --date-from 01/10/2026 --date-to 31/10/2026 --ca-file certs/server.crt
```

Use the certificate that actually signs your application endpoint. Supply an
authorized REST token in `PORTFOLIO_API_TOKEN` and a Brave Search API key in
`BRAVE_SEARCH_API_KEY`; never pass either credential to a model. The selected
host CLI must be installed and signed in. No CLI process runs inside Docker.
Search uses the configured service rather than an unbounded CLI browsing loop.
`--config PATH` overrides `CONFIG_PATH`/`config.yaml`; `--dry-run` researches and
validates without writing.

```yaml
price_agent:
  provider: codex          # or claude
  model: ""               # Codex: gpt-6.1-sol; Claude Code: sonnet
  reasoning_effort: medium
  max_model_calls: 5
  max_rest_calls: 5
  timeout_seconds: 110
  base_url: https://localhost:6443
  search:
    provider: brave
    api_key: "${BRAVE_SEARCH_API_KEY}"
```

Recommendation: start with `gpt-6.1-sol` at medium effort for Codex, or `sonnet`
at medium for Claude Code. Use low after testing straightforward, unambiguous
listings; high is available for difficult evidence, without increasing call
ceilings. OpenAI's [GPT-6.1 Sol model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
describes it as a lower-cost choice for complex work and supports medium effort.
Model access depends on the signed-in account.

One user update request gets at most five model decisions and five application
REST attempts, including failed calls; YAML values above five are capped.
Each CLI invocation is a single tool-free planning turn. The controller owns
allowlisted internet search, source reads, writes and verification; a separate
five-call internet budget also bounds research. It normally uses three REST
calls: metadata GET, one batch PUT, verification GET. It reserves the last two
before writing. Reusing the request object, nested tools, automatic write
retries and model-selected URLs to the application are prohibited. Search
snippets alone cannot support a write. Missing or ambiguous evidence stops it.
Numeric source dates with ambiguous day/month order and comma-decimal price
formats are rejected; API and UI date inputs still accept `dd/mm/yyyy`.
Current-price proposals older than the latest saved day are rejected. Initial
current reads limit returned history, and verification reads only the submitted
date interval; adding older observations remains available in historical mode.
Source pages still require model interpretation; these checks do not guarantee
market-data accuracy. Review `--dry-run` output when appropriate.

`updated` means saved rows were verified. `written_unverified` means the write
returned success but verification failed or disagreed. A failed write can have
an unknown outcome; inspect saved records before a separate user-requested retry.
Call counts are returned even on failure. No real-model invocation or live price
write is performed by the test suite.

#### Missing holding information with AI

Choose **Portfolio → Find missing data with AI** to open the progress popup.
The first permitted menu activation starts one request; reopening an existing
request shows its progress or results without starting another. The popup shows
the current phase, security being checked, checked-work counts and readable
per-security outcomes. Closing it leaves background work running. Starting a
new batch or resuming an interrupted status check is an explicit popup action.
Viewers can inspect results, while updates require Admin/Operator permission.

The action first tries configured data
APIs for a bounded selection of **open holdings only**, including shorts and
reopened positions. Fully closed positions are excluded before model calls.
Remaining gaps can use internet evidence; API-only success and an unavailable
search service do not invoke the model. Both this button and the host skill use
the `price_agent` provider/model/effort settings (Codex by default, or Claude
Code), and internet search uses `price_agent.search` above. The existing `llm`
section supplies the shared host bridge socket and whether AI is enabled;
read-only dashboard chat keeps its separate `llm` model selection.

The CLI sign-in and internet search are separate prerequisites. A signed-in
Codex/Claude CLI does not supply a Brave Search API key. Without that key, the
app keeps ordinary API results, reports `research_unavailable`, and avoids model
calls. Public TreasuryDirect retrieval needs no provider/search key; Finnhub
and EODHD require their own configured access.

Ordinary API preflight has a shared 25-second response budget, with at most three
in-flight checks and deduplication across retries. Slow checks can finish caching
evidence, but the job retains its eligible inventory and continues with the
remaining gaps. It no longer discards a completed inventory because a serial
provider check exceeded the agent REST timeout. Timeout and application failures
have separate safe diagnostics; exception messages and credentials stay out of
public status. Progress counts mean checks completed in that phase, not prices
saved; verified updates are reported separately.

The model sees only allowlisted REST tools under the initiating user's identity.
It never reads or writes databases, files, or shell state. The application alone
validates proposed source-backed values and owns storage behind REST. Supported
missing values are compatible raw Last/Close prices no older than seven calendar
days, company names, and industries. It preserves existing profile values and
retains source evidence. Unsupported fund/bond price conventions, fundamentals,
and distributions remain missing rather than becoming guessed values.

Each click shares at most **five model calls and five agent REST attempts**,
including failures, plus five upstream search/page reads. It processes up to
three candidates; remaining candidates keep a truthful unprocessed status and
are prioritized on a later user request. Polling resumes the same job without
resetting budgets. Per-security friendly outcomes appear in tooltips and the
result details and are recorded in market-data logs. Prices and missing fields
are refreshed after completion; positions closed during research are skipped.

Registered U.S. bonds with a CUSIP/ISIN can fetch API reference prices, history
and terms even when registered locally without a stock ticker. Security history
returns these separately as `market_data`; cached snapshots can identify the
actual provider in holdings. Registration origin does not establish whether a
price feed is available. API percent-of-par quotes retain their dates, basis,
side and units per $100 face. They are not inserted into currency-per-unit price
history or applied to portfolio valuation without an explicit quantity/par-unit
mapping. Existing local valuation evidence stays separate. Treasury programme
purchase/redemption reference values are not relabeled exchange closes, clean
prices or executable quotes; partial historical coverage remains explicit.

| Method | Route | Authorization and purpose |
| --- | --- | --- |
| POST | `/api/securities/enrichment/ai` | Admin/Operator starts or obtains their existing active job; browser CSRF required |
| GET | `/api/securities/enrichment/ai/{request_id}` | Initiating user's job status |
| GET | `/api/securities/enrichment/status` | Authorized persisted outcomes and current user's active job |
| GET | `/api/securities/enrichment/candidates?request_id=...` | Own running Admin/Operator job; application inventories and tries ordinary APIs once |
| GET | `/api/securities/enrichment/security?request_id=...&security_key=...&field=auto` | Own running job and approved candidate; bounded source research |
| POST | `/api/securities/enrichment/ai/{request_id}/finalize` | Own ready job only; server validates/applies bound evidence; browser CSRF required |

All business REST routes retain authentication, role authorization, REST token
access mode, and browser CSRF enforcement. Read-only identities cannot start or
finalize updates. Repeated clicks deduplicate active jobs instead of spawning
unbounded agents. A missing source or configuration produces an actionable
per-security result, without exposing credentials or raw provider exceptions.

### Application diagnostics

Application logs are stored in `data/logs` on the host (`/app/data/logs` inside Docker), so they survive container crashes and replacement. Separate files cover `application`, `http`, `auth`, `portfolio`, `market-data`, and `chat`. Each record is flushed and synced to disk. Full files rotate into ZIP archives; the oldest archives are deleted. If a main log is missing after a restart, it is recreated.

Admins can change **Settings → Logging** globally. Defaults are **10 files per component, including the current log**, and **10 MB per current file**. Changes apply immediately and persist across restarts. Chat-history and logging-settings changes do not invalidate financial analytics.

Docker's separate stdout/stderr capture also defaults to ten 10 MB files with compression. Its engine-level limits are configured through Compose (`CONTAINER_LOG_MAX_SIZE` and `CONTAINER_LOG_MAX_FILES`) when recreating the container; the in-app settings control the component files in `data/logs`.

Chat diagnostics record redacted prompts/context, model exchanges, approved REST reads/results, unsupported reasons, and errors. Passwords, API keys, tokens, cookies, authorization values, credential-bearing URLs, and configured secrets are redacted before writing or ZIP rotation. Chat authors show the authenticated user's full name; ordinary answers omit source footers. Unsupported requests and failures receive localized messages with a server-generated UUID. Search that UUID in `chat.log` or the minimal correlation events in `docker compose logs`; source paths and detailed diagnostic evidence stay in the log rather than the answer. The read-only model has no tool for reading logs, changing logging settings, or writing portfolio records.

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
