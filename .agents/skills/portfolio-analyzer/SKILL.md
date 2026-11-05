---
name: portfolio-analyzer
description: Build or modify portfolio-analysis tools with local portfolio data and optional read-only external PostgreSQL import sources, including Dockerized HTTPS dashboards, account ownership, holdings filters, stock/bond enrichment, fundamentals and dividend trends, support/resistance, moving averages, volume analysis, FX currency display, stock screening, and scheduled alerts.
---

# Portfolio Analyzer

Build portfolio dashboards, screeners, import workflows, and alerts around a local source-of-truth database with optional read-only external portfolio imports.

## Core Workflow

1. Read the user's YAML config requirements and keep secrets server-side only. External import settings may include database host, port, database, username, and password; never put these values in frontend bundles, logs, screenshots, or browser-visible API responses.
   - Never log passwords, API keys, auth tokens, connection strings, or credentials to the browser console, backend logs, screenshots, or user-visible diagnostics. When adding console logs, log only safe operational details such as endpoint names, durations, counts, statuses, and sanitized error types/messages.
2. Inspect the target repo before choosing a stack. If no app exists, prefer a Docker Compose service with:
   - Backend API: Python FastAPI or Node/Nest/Express.
   - DB access: PostgreSQL client with parameterized queries.
   - Scheduler: backend cron/job loop, not browser timers.
   - Frontend: React/Vite or the repo's existing UI framework.
   - HTTPS: listen on container port `6443` with a mounted certificate/key or generated self-signed cert for local use.
3. Read `references/implementation-guide.md` before designing queries, data-provider adapters, metrics, alerts, or the dashboard surface.
   - For UI features or fixes, automatically apply `$principal-ux-engineer` before implementation, even when the user does not mention UX. For functional changes, use `$principal-engineering-triad` to route implementation and fresh independent QA when delegation is available and permitted. Keep small copy/style corrections proportionate and disclose a same-agent QA fallback.
4. Validate by running available tests/builds and by checking the dashboard loads locally. For frontend work, inspect responsive desktop and mobile screenshots when practical.
   - Replay the user's action sequence and verify the affected financial result after reload. Label synthetic fixtures and isolated renders; do not report them as live application verification. Respect an existing user review-round limit.
5. When asked to commit and deploy a repository that contains `scripts/commit-and-deploy.sh`, use `./scripts/commit-and-deploy.sh "<commit message>" <explicit task-owned file>...` for the release instead of separate commit and deployment commands. Targeted development and independent QA checks may run beforehand; the script still runs its own required validation, scoped commit, Docker Compose rebuild, and HTTPS health check. Pass only task-owned changes and exclude unrelated user edits. If the script fails, diagnose the failed gate and do not bypass it unless the user explicitly requests that.
   - Honor explicit in-scope commit/deploy authorization already granted. Verify that the build context also excludes unrelated worktree changes, including mixed files; preserve those edits exactly. After release, verify the deployed revision and affected behavior, not only the health endpoint.

## Required Capabilities

For a new tool, select the capabilities required by the requested product. For changes to an existing application, apply the relevant rules below within the user's scope; do not implement unrelated missing capabilities merely because this skill lists them.

- Import holdings from an explicitly configured read-only portfolio source, including securities and bonds where the source schema exposes them.
- Support a separate local portfolio database, independent from the external source, for user-managed accounts, manual securities, transactions, historical prices, account reports, and retirement fund records. Link accepted external holdings to existing local accounts, and never write local edits back to the external source.
- Require every local account to have at least one person. Require exactly one person for Long-Term Savings and ESOP accounts; allow multiple people for Investment and Bank accounts.
- Require every pension, provident, or savings-fund record to use a Long-Term Savings account and inherit its single person automatically. Do not ask for a second person assignment on the fund.
- Never auto-create an unassigned account during external import. Skip only the unmapped or invalid account and its data, continue importing valid accounts, and return actionable skipped-account details for manual recovery.
- Allow account management with add/update/remove flows. Accounts should include type (`Investment`, `Long-Term Savings`, `Bank`), location/country, currency, initial cash, username, account id, management company, and comments.
- Support manual securities and transactions without automatically changing cash. Users should be able to add/remove securities and record buy, sell, and short actions with symbol, quantity, entered price, stock market, asset class, date, and comments.
- Normalize entered prices by market convention: US equities use dollars, US bonds use cents, and Israeli securities use agorot where 100 agorot equals 1 ILS. Store normalized currency prices server-side and keep the original entered price for audit/display.
- If a symbol cannot be found through configured providers, return a clear validation error and allow the user to explicitly add it manually with manual prices.
- Support manual historical price add/update/remove flows and use local historical prices for account value and profit trend reports.
- Provide account trend reports by date range showing account value and percent profit, with filters by account, account type, location, and value range.
- Support pension/provident/savings-fund records. Pension calculations should show estimated monthly payout as saved amount divided by a configurable factor, defaulting to `200`; each record should support id, amount, factor, kind, and comments.
- Show the primary portfolio value as a total converted to ILS when ILS is the dashboard base currency, using configured FX rates. Show account-level value chips below the total, with tooltips naming the account and attached securities.
- Include a first-screen frame for pension/long-term-savings accounts and pension/provident/savings fund records, not only a modal.
- Allow portfolio filters by account, platform, asset class, symbol, currency, country, sector, industry, holding size, realized/unrealized profit, dividend yield, and custom search criteria when data is available.
- Show high/min price over 5 years, 3 years, 1 year, and 1 month.
- Show income trend, profit trend, dividend trend, profit/market-cap trend, industry, and percent increase/decrease with positive/negative/neutral color semantics.
- Show a clear missing-data icon and status text when a provider lacks data for a metric, period, bond, or non-covered exchange.
- Calculate support/resistance over 1 month, 1 year, 3 years, and 5 years.
- Calculate moving averages for 7, 10, 15, and 30 trading days.
- Analyze volume with current volume, average volume, and relative volume trend.
- Support user-added display currencies such as `USD/ILS` using an FX provider adapter.
- Provide a stock search/screener over income, profit, dividend, trend direction, growth percentages, and profit/market-cap metrics.
- Provide scheduled alert rules that run daily and notify when a stock matches saved screen criteria.

## Financial Data After Portfolio Changes

Any change to transactions, accounts, ownership, instruments, prices, imports, cache invalidation, or dashboard loading must preserve and refresh the financial analytics shown for current holdings. Reuse saved market evidence independently of the portfolio aggregate cache; never replace available reports or dividends with local-only missing placeholders. Apply the recurrence checks in [Corrections and Derived Financial State](references/implementation-guide.md#corrections-and-derived-financial-state) before completing such changes.

## Keep In-App Help Current

Every added, changed, or removed functionality must include an update to the affected in-app Help entries in the same task, before completion or release. In this repository, maintain the Help dialog in `web/index.html` and its Hebrew translations in `web/i18n.js` together. Cover the actual navigation, prerequisites, inputs and units, steps, results, relevant permissions, and loading/missing/error/retry or cache behavior; remove instructions for obsolete controls. Verify explanations against the implemented UI, API, and calculations rather than inferring behavior from labels or old Help text.

Check that every exposed navigation feature and settings workflow has useful guidance, and verify the updated Help in both Hebrew and English. Report which Help entries changed and any verification limits. Cosmetic-only changes need a Help accuracy check, without adding filler descriptions of styling. An audit of all Help must compare every existing section and current navigation/settings feature against implementation, not only the most recent change.

## Data Providers

Prefer a provider abstraction and cache responses locally. Free market-data APIs have changing limits and incomplete coverage, so implement graceful fallback and missing-data states.

Recommended order:

1. Alpha Vantage for documented free APIs covering equities, fundamentals, dividends, FX, and technical indicators when request volume is low.
2. Financial Modeling Prep when the user has or can create a key and needs richer fundamentals, profiles, market cap, statements, dividend, or growth endpoints.
3. Stooq CSV as a no-key fallback for historical daily OHLCV where symbol coverage is adequate.
4. Yahoo Finance or Google Finance only as explicitly enabled, best-effort fallback adapters. Treat both as unofficial/unsupported for programmatic access; isolate them behind provider interfaces, rate-limit aggressively, cache responses, and show degraded-provider warnings in the UI.

Do not use unofficial scraping for a dashboard unless the user explicitly accepts the maintenance and licensing risk.

## Metrics

Use adjusted close for price history when available. Compute percent change as `(current - prior) / abs(prior) * 100`; if `prior` is zero or missing, return a missing-data state rather than a misleading percent.

For trends, store the raw series, the selected period, the percent change, and a direction enum: `up`, `down`, `flat`, or `missing`. Let the UI map these directions to colors. Do not encode colors in business logic.

For support/resistance, use deterministic heuristics: local extrema, recent swing highs/lows, clustering within a tolerance band, and volume confirmation. Label derived levels as estimates.

## Risk Scoring

For an existing application, its maintained versioned risk model governs over
the new-model recommendations below. In portfolio-analyzer, read the
[maintained portfolio-risk model](../trade-simulation/references/portfolio-risk.md)
before changing risk scores, borrowing, cash buffers, or account rollups. Preserve
its declared formula and keep heuristic scores separate from loss probabilities.

Use a 0-100 risk score for accounts and for the total portfolio, where `0` means very low portfolio risk and `100` means extreme concentration/speculation risk. The score is a weighted sum of capped component scores:

`risk_score = clamp(round(concentration + asset_mix + currency + industry + cash + options + data_quality), 0, 100)`

Recommended component weights:

- Position concentration, 0-25 points: combine top holding weight and HHI. `top_weight_score = min(top_position_pct / 40, 1) * 15`; `hhi_score = min(sum(position_pct^2) / 2500, 1) * 10`, where percentages are 0-100 weights inside the account or portfolio.
- Asset mix, 0-20 points: weighted average by asset class risk. Suggested factors: cash `0.05`, government bond `0.20`, investment-grade bond `0.35`, broad ETF/fund `0.45`, equity `0.65`, sector/single-country fund `0.75`, commodity/crypto/other `0.85`, option/future/leveraged instrument `1.00`. `asset_mix = weighted_factor * 20`.
- Currency exposure, 0-15 points: compare non-base-currency exposure to total value. `currency = min(non_base_currency_pct / 80, 1) * 10 + min(largest_foreign_currency_pct / 60, 1) * 5`. If liabilities/spending currency is known, use that as base; otherwise use dashboard base currency.
- Industry variety, 0-15 points: use sector/industry HHI plus missing classification penalty. `industry = min(industry_hhi / 3000, 1) * 10 + missing_industry_pct / 100 * 5`. Well-diversified broad ETFs can be treated as diversified unless look-through holdings are available.
- Cash buffer, 0-10 points: cash reduces risk until it becomes excessive drag. If cash is 5-20% of value, score `0`; if below 5%, score `(5 - cash_pct) / 5 * 6`; if above 20%, score `min((cash_pct - 20) / 50, 1) * 4`.
- Options, leverage, and derivatives, 0-10 points: `options = min(options_or_leveraged_pct / 25, 1) * 8 + uncovered_short_or_margin_flag * 2`.
- Data quality, 0-5 points: add risk when key data is missing. `data_quality = missing_price_pct / 100 * 2 + missing_sector_pct / 100 * 1.5 + missing_currency_or_asset_class_pct / 100 * 1.5`.

Calculate account risk from positions within that account. Calculate total portfolio risk from all accounts combined, with an optional account-risk rollup for explainability:

`total_risk = clamp(round(0.75 * combined_holdings_risk + 0.25 * nav_weighted_account_risk), 0, 100)`

Risk bands for display: `0-20` low, `21-40` moderate, `41-60` elevated, `61-80` high, `81-100` extreme. Always show component breakdowns and the top risk drivers, not only the final number.

Advanced risk scoring should add suitability and market-risk proxies when data is available while preserving the 0-100 scale. Recommended advanced component caps: concentration `16`, asset mix `14`, currency `10`, industry `10`, cash `7`, options/futures/leverage `10`, volatility `10`, family-member horizon suitability `10`, issuer/country concentration `8`, and data quality `5`. Use family birthdays on accounts/funds to estimate time to age 67, penalizing high-risk exposure for short horizons and under-risking for long horizons. Use historical return volatility when available; otherwise use a transparent proxy from 1Y high-low range. Treat futures with options and leveraged instruments in the derivatives bucket. Treat broad ETFs/funds as diversified proxies unless look-through holdings are available; sector, thematic, leveraged, or concentrated funds should not receive this diversification benefit. Display risk with color and a distinct symbol per band, and put the formula, min/max, component values, and top drivers in the tooltip.

## Dashboard

Make the first screen the actual analysis dashboard, not a marketing page. Use dense, readable tables/charts with filters, sortable metrics, provider-status badges, missing-data icons, and alert controls. Avoid storing credentials in localStorage.

Keep interface copy concise and useful. Omit decorative labels and eyebrow text that repeat a nearby heading or add no information needed for a decision or action. For example, omit "Matches" / "התאמות" above "Active signals", "Automation" above "Saved rules", and "Audit trail" above "Run history". Preserve meaningful field labels, instructions, statuses, and accessibility names.

Use compact finance-dashboard typography: Inter with 400/500/600/700/800 weights, near-black or dark navy surfaces, quiet strokes, and graph styles appropriate to the data. Use bar charts for category/ranked holdings and P/L comparisons; reserve line/area charts for real time-series data.

Apply principal-level UX review before shipping UI changes. Row-level actions such as Edit, Remove, Delete, Use, Attach, and Sync must be compact controls aligned with the row action area, usually on the right. Do not let secondary/destructive row actions stretch across a content row or consume a full line unless the user explicitly asks for a full-width touch target. Use full-width buttons only for primary form actions, modal footers, or intentionally stacked mobile layouts.

Use professional UI copy and casing for profile/account metadata. Prefer labeled facts such as `Birth Date`, `Retire Age`, and `Age` over rough inline fragments like `retire` or `age`; keep labels scannable, consistently capitalized, and visually separated when multiple facts appear in a row.

All user-facing dates in forms, tables, chart labels, tooltips, reports, pension/family-member workflows, and settings must display and accept `dd/mm/yyyy`. Keep backend storage and provider/API integrations internally normalized when useful, but convert at the UI/API boundary so users do not see ISO `yyyy-mm-dd` dates. Date-picker popups must be anchored beside their field on the side facing the viewport center and clamped inside safe viewport margins; in RTL layouts, never anchor a hidden native date input to logical inline-start because that can place the browser popup at the far-right screen edge.

Use one shared country and currency presentation contract throughout the application, including account, broker, company-option, security, price, report, filter, and read-only summary surfaces:

- Keep stored values and API payloads stable and locale-independent: ISO 4217 currency codes and canonical country values/codes. Localize labels only at the UI boundary.
- Exclude the `PS` region entry and its `Palestine` / `פלסטין` labels from every application country catalog, selector, datalist, and autocomplete surface. Keep the exclusion in the shared country source so it applies consistently in every language and workflow.
- Display a country according to the interface direction: English/LTR uses `flag emoji + localized country name` (for example `🇮🇱 Israel`), while Hebrew/RTL reverses the composition to `localized country name + flag emoji` (for example `ישראל 🇮🇱`). Apply Unicode bidirectional isolation to mixed-script option and metadata labels so the flag stays attached to the country and Latin broker names do not reorder adjacent Hebrew text. Do not show a bare country code or an unflagged country name when the shared country formatter can resolve it.
- In every Hebrew currency field and read-only currency label, place the currency symbol visually on the left and the localized full name on its right. To achieve that reliably inside an RTL control, construct the logical text as `localized full name + symbol` and wrap the complete label in RTL bidirectional isolation. Display English as `symbol + ISO code`, for example `₪ ILS`, `$ USD`, and `€ EUR`. Do not use raw `ILS`, `USD`, or `EUR` as the visible select label.
- Managed accounts, brokers, and employee stock-option workflows should use the same supported currency set (`ILS`, `USD`, and `EUR`) unless the product requirements explicitly expand it. Market-data tools may expose additional ISO currencies, but must format them through the same shared currency formatter.
- Reuse centralized option/label helpers for selectors and read-only metadata; do not build separate raw country or currency option lists per modal. Preserve the selected stored value when the language changes and refresh visible labels immediately.

Keep the sidebar navigation hierarchical unless the user directly asks to change it. Preserve parent menu groups for related sections, such as dashboard/reporting, portfolio data, household/retirement, markets/alerts, and system/settings, instead of flattening all navigation items.

Keep portfolio loading non-blocking unless the user directly asks to change it. The app shell must remain usable while portfolio analytics load in the background; show loading only as a lightweight topbar/status indication, not as a blocking overlay or modal.

Honor the active interface language completely. Persist machine-readable status values in backend data, but localize every user-visible status, action, count label, error summary, badge, tooltip, and empty state at the UI boundary. A Hebrew interface must not expose English operational labels; an English interface must not expose Hebrew labels.

## Alerts

Represent alert rules as structured JSON/YAML criteria and evaluate them on the backend daily. Include last-run time, matched symbols, provider errors, and notification status. If no notification channel is specified, implement in-dashboard alerts and leave email/webhook/Telegram as pluggable adapters.
