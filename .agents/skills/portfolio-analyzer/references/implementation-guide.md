# Implementation Guide

## Configuration

Use a YAML file with this shape, adapting names to the target repo:

```yaml
external_import:
  db:
    host: "localhost"
    port: 5432
    database: "portfolio_source"
    username: "portfolio_reader"
    password: "change-me"
    ssl: false

market_data:
  primary: "alpha_vantage"
  fallback: ["financial_modeling_prep", "stooq"]
  experimental_fallback: []
  cache_ttl_hours: 24
  alpha_vantage:
    api_key: "${ALPHA_VANTAGE_API_KEY}"
  financial_modeling_prep:
    api_key: "${FMP_API_KEY}"
  yahoo_finance:
    enabled: false
  google_finance:
    enabled: false

dashboard:
  https_port: 6443
  display_currencies: ["USD", "ILS", "USD/ILS"]

alerts:
  schedule: "0 7 * * *"
  timezone: "Asia/Jerusalem"
```

Load `${...}` values from environment variables when possible. Permit literal passwords because the user requested it, but warn when committing a config file and include the file in `.gitignore`.

## External Portfolio Source DB Access

External portfolio schemas can change by source version. Inspect the live database or source migrations before writing final SQL, keep access read-only, and isolate source-specific mappings behind an adapter.

Start discovery with:

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;
```

Then inspect columns for candidate tables:

```sql
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name in ('Order', 'SymbolProfile', 'Account', 'Platform')
order by table_name, ordinal_position;
```

Expected concepts to map:

- Orders/transactions: symbol, date, activity type, quantity, unit price, fee, currency, account.
- Symbol/security profile: symbol, name, asset class, currency, country, sectors/industry if present.
- Accounts/platforms: used for filtering and attribution.

If bonds are represented as custom assets or activities, surface them with available cost, income, maturity/coupon fields if present, and mark unsupported market-data metrics as missing.

## Provider Adapters

Expose a small internal interface:

```ts
interface MarketDataProvider {
  prices(symbol: string, from: Date, to: Date): Promise<Ohlcv[]>;
  fundamentals(symbol: string): Promise<FundamentalSeries>;
  dividends(symbol: string): Promise<DividendSeries>;
  profile(symbol: string): Promise<CompanyProfile>;
  fx(pair: string): Promise<FxQuote>;
}
```

Use provider-specific adapters behind this interface. Normalize all dates to UTC ISO dates and currencies to ISO 4217 codes. Cache normalized responses in the app database or a local SQLite/Postgres table keyed by provider, symbol, endpoint, and date range.

Yahoo Finance:

- Do not present Yahoo Finance as an official API. Its old public finance API was discontinued; current libraries such as `yfinance` use unofficial/public web endpoints.
- Use only when the user explicitly enables it for personal/internal use and accepts that it can break, rate-limit, or have licensing constraints.
- Prefer it for historical prices/dividends only, not as the source of truth for production alerts or redistribution.

Google Finance:

- Do not present Google Finance as an official REST/JSON API. The historical Google Finance API was shut down, and current access is through the website, Google Sheets `GOOGLEFINANCE`, or third-party scrapers.
- Avoid Google Sheets as a backend data provider for this dashboard because historical data access is limited and operationally fragile.
- Use Google Finance only as an explicitly enabled experimental fallback for display-oriented fields when the user accepts scraping/provider risk.

## Metric Definitions

Price high/min:

- Periods: 1 month, 1 year, 3 years, 5 years.
- Source: adjusted OHLCV where available.
- Output: high, low/min, dates of high/low, current price, percent from high, percent from low.

Income trend:

- Prefer revenue or total revenue from annual and quarterly income statements.
- Show absolute values and percent change for the chosen period.

Profit trend:

- Prefer net income; optionally include operating income when available.
- Show absolute values and percent change.

Dividend trend:

- Use paid dividend amounts by ex-date/payment date where available.
- Show absolute amounts per year/quarter and trailing-12-month total.

Profit/market cap:

- Compute `net_income_ttm / market_cap` when both are available.
- Label as an earnings-yield-like ratio; avoid calling it valuation advice.

Industry:

- Prefer provider company profile industry; fall back to external source symbol-profile metadata.

Support/resistance:

- Run per period: 1 month, 1 year, 3 years, 5 years.
- Find local highs/lows with a configurable lookback window.
- Cluster levels within 1%-2% or an ATR-derived tolerance.
- Rank by touch count, recency, and volume near level.

Moving averages:

- Compute SMA for 7, 10, 15, and 30 trading days from adjusted close.
- Include price-vs-MA and MA slope direction.

Volume:

- Include latest volume, 20-day average, 90-day average, relative volume, and trend direction.

## Filtering And Search

Filters should work independently and combine with AND semantics by default:

- Portfolio metadata: account, platform, asset class, currency, country, sector, industry.
- Holdings: symbol/name search, position value, quantity, allocation, unrealized profit/loss, realized profit/loss.
- Fundamentals: income/profit/dividend growth direction, minimum percent increase, maximum decrease, missing-data inclusion.
- Technicals: near support/resistance, above/below moving averages, relative volume threshold.
- Valuation proxy: profit/market-cap minimum/maximum.

Return clear result metadata: matched filters, last refreshed time, provider used, and missing-data count.

## Corrections and Derived Financial State

In this repository, portfolio heatmap, correlation, X-Ray, dividend calendar,
benchmark comparison, trading journal, mean-variance optimization, VaR and
portfolio buy/sell/watch alarms include only authoritative account records whose
type is exactly `Investment`. Apply `app.investment_scope.investments` at engine
boundaries; never infer eligibility from a holding label or default an unknown
account type. Exclude ESOP/RSU, Bank and Long-Term Savings accounts from selectors,
holdings, cash, transactions and snapshot aggregates. Preserve journal notes and
legacy benchmark inputs while keeping excluded-account history out of results.
Reproduce account reclassification, stale selected-account recovery, journal
shortcut visibility and aggregate benchmark membership changes when altering
these paths.

Imported market fields may name a source such as `YAHOO` rather than an exchange.
Do not discard its existing cache automatically or assume a US listing. Resolve
it through saved recognized exchange metadata and compatible currency before
using cached prices, keeping unknown identity unavailable. Reproduce a provider
label with saved Nasdaq/NYSE metadata and a recent cached price pair, then a
currency mismatch or missing exchange; analytics reads must not fetch providers
or substitute undated cost basis for a current price.

Heatmap rectangles preserve exposure proportions while fitting labels against
their measured rendered dimensions, including resize and font-load changes.
Wrap long symbols before omitting secondary labels; keep full hover, keyboard
and touch details available. Stocks/Bonds/Funds filters govern totals, weights,
account panels and missing-value lists together. Bond values use already
normalized currency per unit. Unrealized P/L follows the ledger's long/short
remaining-cost convention; current-FX conversion is not historical ILS return.
Use plain Hebrew such as `נייר ערך במפה` and
`החזקות שלא מוצגות במפה`, avoiding the unclear word `אריח`.

Broker administration keeps the institution list separate from the New/Edit
popup. Cancellation leaves data unchanged; saving protects against duplicate
requests, stale editor/session responses and draft loss on errors. Nested popup
focus returns to the parent broker list. Broker administration is not restricted
to Investment accounts; that restriction belongs to investment analytics.

- Trace financial discrepancies from the persisted ledger and original entered units through normalization, cost basis, cash movement, saved history, conversion, API payloads, and the displayed chart. Verify the live data source and record timestamps; isolate and sanitize reproductions without editing runtime data during diagnosis.
- Treat user-entered statement balances and automatically calculated history as different sources. Define and explain override precedence; missing or blank values must not silently become authoritative zero balances. An explicitly entered zero remains a valid distinct value.
- When a transaction is added, edited, deleted, moved between accounts, or moved to another date, refresh or invalidate all affected calculated history and caches. Include both old and new accounts and dates. Preserve independent manual observations according to the application's explicit rules.
- Keep ledger mutation and derived-state updates atomic, or use a documented recoverable/versioned invalidation mechanism. A successful edit must not leave the interface reading stale calculated balances. Reconcile pre-existing stale derived records through the corrected application path when authorized, with a backup and audit evidence.
- Verify a regression sequence that enters an incorrect price or unit, saves it, corrects it, reloads, and checks the ledger, cash, history, and totals. Include missing input, explicit zero, partial and full closure, date/account changes, deletion, and rollback cases where relevant.
- Current cash updates reconcile a finite signed target against known account-currency ledger cash on today's Jerusalem date. Persist the difference as a local `cash_adjustment` with `CASH_IN` / `CASH_OUT`, positive quantity and raw currency price 1; never reinterpret it as income, fees or a security trade, and never rewrite opening cash. Reject unknown, mixed-currency or future cash evidence. Recompute and compare the cash revision inside the write transaction; replay committed request IDs without duplicating movements. An unchanged target creates no ledger row, and a stale no-op revision cannot overwrite later activity. Rebuild affected daily snapshots atomically while preserving manual observations and earlier dates. Keep dashboard, reports, history, risk, planner, simulator and VaR cash handlers aligned. Imports preserve the local cash anchor after reconciliation and report that precedence; currency changes must not reinterpret existing adjustments. Generated cash entries are excluded from positions and security editing.
- Account-history points declare `native_currency`, `native_available` and a reason when unavailable. Native history uses recorded account units without dashboard FX; total native views combine only accounts of one currency and become unavailable when any contributing observation is invalid. Mixed-currency computed evidence, including closed cash movements, remains a gap. Daily snapshots inherit calculated eligibility; explicitly supplied non-daily snapshots retain their recorded precedence. Account denomination follows the current account declaration because legacy snapshots have no separate historic currency. Recorded P/L is not a flow-adjusted period return, and account-value changes are not investment profit. Currency-exposure amounts are equivalents, not cash balances; validate source and conversion rates before showing them.
- For trade-history reporting, work from the complete recorded ledger, including zero-quantity positions. An imported position snapshot is not evidence of its original purchase date or complete trading history; expose unavailable duration or basis rather than inventing them. Keep realized and unrealized P/L, fees, income, and any annualization formula explicit.
- For duration and P/L reporting, inspect existing cost-basis and trade-order contracts before choosing episode or lot rules. State how partial exits, re-entry, short covering, transfers, fees, and income affect the result. Distinguish a monetary annualization from a percentage return; honor the user's requested formula and identify its units. A missing opening date or zero elapsed days makes a per-day or per-year division unavailable, rather than justifying an invented date or a one-day denominator.

## Alerts

Store alert rules as structured records:

```json
{
  "name": "Dividend growth candidates",
  "enabled": true,
  "criteria": {
    "dividendTrend": "up",
    "profitTrend": "up",
    "minProfitMarketCap": 0.04
  },
  "notification": {
    "channels": ["dashboard"]
  }
}
```

Run daily via cron inside the backend container or a dedicated worker. Persist run history so the UI can show whether "no matches" means no qualifying stocks or a failed provider call.

## Docker And HTTPS

Expose HTTPS on port `6443`.

Recommended Compose shape:

```yaml
services:
  portfolio-analyzer:
    build: .
    ports:
      - "6443:6443"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./certs:/app/certs:ro
    environment:
      CONFIG_PATH: /app/config.yaml
```

For local development, generate a self-signed certificate only if cert files are missing. For production, require user-provided certs or a reverse proxy.

## UI States

Use these metric states consistently:

- `ok`: render value and trend.
- `stale`: render value with provider/status warning.
- `partial`: render available series with gaps called out.
- `missing`: render a missing-data icon plus a short label such as "No dividend data".
- `error`: render retry/status details without exposing secrets.

Never hide a holding solely because market-data enrichment failed unless the user selected a filter that excludes missing data.

### Cached Analytics and Refresh Lifecycle

- Separate retaining financial evidence from considering it fresh. SEC companyfacts and ticker metadata may remain saved indefinitely for offline use, but online provider reads must enforce the configured refresh interval. Refresh expired raw data from official endpoints, replace it only after a valid successful response, and preserve old raw/normalized evidence and honest stale status on failure. A new as-of cutoff can be reconstructed from retained raw facts without downloading again; filter by filing date to prevent lookahead. Never reset a failed refresh timestamp or report stale-only availability as a completed no-newer-report check. Regressions: `tests/test_sec_report_refresh.py`.

- In company-outlook UI, label supporting evidence as `Analysis data coverage` / `היקף הנתונים לניתוח` with Broad/Moderate/Limited, and keep it visually neutral. Active v5 coverage measures usable shared financial metrics and comparable peers; count-only rules describe legacy records. Follow the versioned repository [.agents/skills/company-outlook-model/SKILL.md](/etuzon/projects/ai/portfolio-analyzer/.agents/skills/company-outlook-model/SKILL.md) for exact weights, incomplete-score handling, frozen outcomes and prospective validation. Color outlook labels and final-score tiles by outcome strength while retaining readable text; do not imply broad data coverage means a positive forecast. A company report check must process every pending or retryable forecast for that symbol using its own baseline, cutoff and direction; share request-level report results/failures, leave other symbols and completed forecasts untouched, and allow valid siblings to finish after a per-forecast failure.

- Saved forecast cards must show the analyzed annual report date and make clear that pending status concerns comparison with a newer report. Explain score/outlook labels and data-confidence labels through hover/focus tooltips on the existing labels, with no separate info button; distinguish confidence in supporting report coverage from a favorable or certain outcome. State rank scope and direction explicitly (1 strongest, last weakest among the actual compared group); a one-company set cannot establish relative strength. Keep saved evidence immutable when clarifying legacy narrative.

- Saved company-forecast checks need per-card checking, completion, failure and retry feedback. Distinguish never checked from a completed check with no newer report using saved evidence, not transient UI state. Persist checked_at for every completed check separately from evaluated_at/accuracy, preserve it through backup/restore, and show the real local dd/mm/yyyy check time. Legacy no-report outcomes may establish that a check occurred but must not receive invented timestamps. Keep the stored no-new-report explanation visible and attach manual-check guidance to a hover/focus tooltip on the status badge without a separate info control. Provider failures, missing baseline/reports, or stale-only fallbacks cannot establish that no newer report exists; keep the previous completed result and expose retry instead. Preserve other cards' focus/open help during list refresh, distinguish a successful evaluation from a failed summary refresh, and invalidate late history responses on sign-out or user changes. Regressions: `tests/test_company_outlook_evaluation_frontend.py`.

- Security and signal charts must render the selected symbol and a localized loading state immediately. Reuse saved provider quotes before network calls only when they cover the visible date interval; preserve live fallback for gaps and merge local price overrides. Load chart history independently of transaction/price lists, reject superseded symbol/period responses, and expose provider failures or timeouts inside the modal with an enabled retry. Keep true empty history distinct from failed loading, including stale-cache fallback after provider errors. Regressions: `tests/test_security_chart_history_cache.py` and `tests/test_security_chart_loading_frontend.py`.

- Version aggregate caches when adding required quote evidence such as `current_date`. Rebuild legacy undated aggregates from saved dated market/local history without provider I/O or rewriting the ledger/raw cache; a cache refresh timestamp is not a quote date. Keep the actual quote-age checks. For truly stale manual instruments, show the symbol, account, last quote date, and a correctly prefilled price-history action instead of instructing the user to refresh data that has no automatic provider. Cover an upgrade with a still-valid legacy cache, restart/reload, preservation of reports/dividends, and recovery after a real local price update.
- Recompute current holding market value and unrealized P/L when dated market quotes change, using each account's own quantity and remaining cost basis. Keep synchronous, cached-first, background and progress-overlay paths on the same calculation, including ordinary symbols without a secondary symbol. Use the latest valid dated normalized quote; preserve newer local marks, manual-only instruments, cash, realized income and historical observations. Verify the full path from persisted positions through provider refresh and API to visible holding/account totals and browser reload. Tests that only confirm quote availability, or require values to remain unchanged after a quote changes, do not establish valuation correctness.

- Keep the provider's display exchange separate from stored holding identity. Legacy imports may store a provider name such as `YAHOO` in `stock_market`; preserve an evidence-backed company-profile exchange through enrichment, per-account attachment, serialization, cached first response, and reload. Do not rewrite transaction/listing identity to repair a tooltip. Verify a saved profile exchange survives aggregate-cache invalidation and that genuinely missing exchanges stay unavailable.

- Keep per-user assistant chats, conversation context, chat-retention preferences and global logging settings out of financial change signatures. Saving or migrating chat history or changing log retention must not evict portfolio analytics or launch market-data refreshes. Verify create/reply/settings/migration leave the financial token unchanged, while account, transaction and price changes still invalidate it; preserve chats in backups independently.
- Keep portfolio-dependent quantities, costs, account ownership, and calculated history separate from company reports, dividend history, prices, and provider evidence. On an edit, deletion, account move, import, or instrument change, rebuild the displayed analytics against current holdings and start an appropriate background market refresh. Invalidate the aggregate portfolio without erasing independent market evidence.
- Serve saved financial and technical evidence on the first non-blocking response without provider network calls or cache writes. Match symbol, secondary symbol, market, currency, instrument class and listing conventions; an unqualified US ticker does not establish another exchange's instrument. Preserve manual/unlisted instrument restrictions.
- Distinguish refreshing, usable cached data, completed missing data, and failed refreshes. Pending must not display Missing, zero, All data available, or false 100% coverage. Keep values that are known and label unavailable values honestly. Localize loading, completion, failure and retry states in every supported language.
- Dashboard Data gaps count confirmed missing-field occurrences per position, including separate positions in different accounts. Deduplicate repeated field labels within a position; present loading and failed checks separately, including field-level states on an otherwise ready row. Keep row counts, summary and snapshot cards, multiline previews and complete details consistent with the loaded dashboard scope. List every affected security/account and reason; do not truncate diagnostics to the top three fields. The read-only details use loaded evidence, support keyboard and touch, and retain reading position during background updates.
- Use portfolio change/progress notifications instead of repeatedly fetching the complete dashboard while enrichment runs. Keep one lightweight stream open; unchanged idle notifications do not fetch data. Progress updates only the status count, and completion applies one coherent snapshot. Edits and explicit Refresh still reload current source data. Reconnect after transport interruptions while retaining displayed evidence; expose manual Refresh when a snapshot or notification connection cannot load. Guard browser responses, subscriptions and worker publication by the current request/revision/generation so old work cannot overwrite a newer portfolio. Publish cache records atomically. Preserve the entire page footprint, scroll, focus, selection, filters, expanded details and nested scrolling during actual result replacement, including the holdings table.
- Required regression sequence: seed real-format saved SEC/provider reports, dividends and prices; display a portfolio; enter a mistaken transaction; correct quantity/price/date/account; reload; then add/delete a position and change account ownership. Assert current holdings and costs, retained/recomputed financial values, closed-position behavior, currency/market identity, and no request-path provider I/O. Cover an aggregate cache clear, no prior aggregate cache, more than the previous polling limit, out-of-order responses/workers, provider and network failure, explicit retry, and true missing provider data.
- A corrected screenshot, manual cache clear or data refresh is recovery evidence only. Completion requires a durable regression test of the dependency and loading lifecycle; preserve that test in future refactors.

- A background market refresh must be bounded and observable by unique security, not by account-position count. Deduplicate identical listings across accounts; preserve each account's quantities, cost basis and long/short conventions. Use bounded concurrency and a configurable batch time budget, and publish completed securities immediately on the server with distinct queued, updating, ready and failed states. The dashboard deliberately retains its displayed snapshot while reporting aggregate progress, then applies the terminal snapshot once; never mark retained metrics freshly updated based only on a progress notification. On budget expiry retain cached evidence, end pending status and offer retry; reuse still-running requests across retries to avoid overlapping writes and unbounded threads. Re-test mixed fast/blocked/failed securities, duplicate accounts versus different listings, source edits/deletions during work, late completion, retries, exact progress counts, and final partial-failure messages.
