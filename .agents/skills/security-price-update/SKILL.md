---
name: security-price-update
description: Research current or historical prices for Israeli funds and other securities when portfolio-analyzer or the user requests AI price retrieval, and save supported observations through the bounded REST workflow. Use for price research and updates, not trades or forecasts.
---

# Security price update

## Mandatory data-access boundary

**The AI agent must NEVER read or write a database. All application information
and changes must go through explicitly allowed, authenticated and authorized
REST endpoints.** This includes indirect access: do not use SQL, an ORM,
SQLite/PostgreSQL clients, database files, backups, exports or shell helpers to
bypass REST. Do not ask for database credentials or add arbitrary REST routes,
URLs or verbs to the agent's own allowlist. Missing REST capability is a reason
to report the limitation, never a reason to access the database.

Use the initiating user's permitted REST identity; authentication alone does not
grant write permission. Respect role, token scope, read-only access modes and
browser CSRF requirements. Never place authentication credentials in prompts,
answers or logs. The application implements storage internally behind those
endpoints; the agent is not granted access to that storage. Public source
research likewise uses only tools actually exposed to the agent by the calling
environment, with application-run research going through its approved REST tools.

Handle an application request using its security metadata, requested dates and
price basis, and whether it asks for research, a preview or a saved update. Read
missing listing details through the approved application tools; ask for
clarification only when material ambiguity remains. An application research
request does not by itself authorize saving prices.

Use the repository's bounded controller for an authorized price update. It reads
listing metadata, researches evidence, batches a local REST write and verifies
the observations. It never writes to an external import source or places orders.

## Finding prices and history

Choose sources and a research method that fit the instrument and the available
tools. The examples below are starting points, not a required sequence or a
source allowlist. A source or format missing from these examples can still be
useful. The research question and financial meaning govern; today's parser
limitations do not define which instruments have valid prices.

Start with the exact security or fund number, ISIN or ticker and venue. Use the
name, manager, share class and currency to confirm the match. Search the local
language as well as English when helpful. A numeric Israeli identifier is not
proof of an exchange-traded stock; do not invent a ticker suffix or substitute a
similar fund or another listing.

Prefer directly published issuer, fund-manager, exchange or regulatory evidence
when it supplies the requested data. Reputable financial portals, documented
provider APIs and authorized broker exports can also supply useful prices or
corroboration. Follow actual links and inspect the dated records; do not invent
API URLs or assume a page's chart controls prove that its underlying history was
retrieved. Where supported by the environment, readable pages, rendered browser
views, downloads and structured responses are alternative ways to inspect the
evidence. Automated application runs must stay within their exposed tools and
shared request budgets.

For a current request, find the latest published observation and report its
actual valuation or trading date. Keep publication and retrieval times separate.
A page updated today can contain an older price. For history, look for a dated
table, chart series, downloadable file or documented historical endpoint. Check
coverage, ordering, pagination and units; retrieve only the requested scope.
Keep one security/share class and a consistent price and adjustment basis. Missing
days remain missing rather than becoming invented observations.

## Israeli funds

Search using the Israeli fund number and its Hebrew name. Useful search terms
include `מחיר פדיון`, `מחיר יחידה`, `מחיר קנייה`, `שערים היסטוריים`, `נתונים היסטוריים`
and `NAV`; choose the terms that match the requested field. Fund-manager pages
and MAYA/TASE disclosures are useful primary starting points. TheMarker Finance,
Funder and Bizportal are examples of additional places to investigate, without
assuming any particular site's availability, freshness or complete coverage.

For example, `5139324` identifies **מור (00) כספית ניהול נזילות**. Its
[MAYA page](https://maya.tase.co.il/he/funds/mutual-funds/5139324),
[TheMarker page](https://finance.themarker.com/mtf/5139324) and
[Funder page](https://www.funder.co.il/fund/5139324) are discovery leads, not
permanent guarantees of usable price evidence. Use the same identification
approach for other fund numbers; do not reuse this fund's prices or dates.

When the application's approved tools expose the Israeli fund REST lookup,
prefer its official MAYA current/history observations before web research. The
public source currently exposes an identity/current record and a bounded history
page; the application handles those provider requests. Preserve ratesAsOf or
tradeDate, not fund-assets dates or retrieval time. Domestic ordinary ILS fund
prices use agorot per issued unit even when nominal value differs; do not multiply
by nominal value. Fund redemption is the dashboard's declared held-fund policy,
while purchase remains separate. In other environments discover suitable official
sources using the tools actually available; these routes are useful leads, not
restrictions on other reliable methods.

Use the instrument type to guide discovery: stock searches use share-price
terms; fund searches may use redemption/NAV terms. A numeric Israeli security
number alone does not prove the instrument is a fund. Source-page read failures
mean the controller could not read those pages, not that no price exists. Keep
those failures separate from empty results, wrong identity or insufficient
dated/unit evidence, and preserve the request's remaining budget.

When checking the application's AI, a successful reviewing-agent lookup is a
required acceptance benchmark: if the agent can retrieve supported public facts,
the application must be able to retrieve them through its allowed tools too.
Trace and fix discovery, source-reader, tool-access and validation gaps, then
verify the real application path with the same identity, observation dates,
units and requested fields. Chat results, indexed snippets and passing mocks
alone cannot prove the application's retrieval or saved update. Do not relax
evidence checks, database restrictions or call limits to claim parity; record
an unexecuted or failing acceptance check explicitly.

Read the source's field definition. Published unit value/NAV, redemption price
(`מחיר פדיון`) and purchase price (`מחיר קנייה`) can have different meanings;
preserve the selected basis rather than silently treating them as a stock's last
trade or close. A daily fund valuation does not imply an intraday market quote.
If the application leaves the required fund price basis ambiguous and the
distinction changes the result, clarify it instead of choosing silently.

Verify whether that source quotes agorot, shekels, a per-unit value or another
explicit scale. Currency and quote unit are separate facts. Do not assume every
Israeli webpage uses agorot, and do not derive unit prices from fund size,
percentage returns or a rebased performance chart. Historical records must retain
their actual valuation dates and the same fund class and price basis.

## Other securities

For U.S. bonds, mutual funds and ETFs, the `us-bond-fund-data` skill describes
identifier-based automatic retrieval through `GET /api/security/market-data`
and flexible research sources. Prefer an available provider response before
asking the user to enter prices manually. Fetching data is separate from saving
a local price override; preserve the returned units, basis and coverage.

Use the instrument's own conventions rather than extending fund rules to every
security:

| Instrument | What to establish |
| --- | --- |
| Shares and exchange-traded funds | Exact listing, quote currency, last/close and session/date; keep an ETF's market price separate from its NAV. |
| Bonds | Identity, clean/dirty basis, accrued-interest treatment and whether the quote is currency, cents or percent of par. |
| Options and similar contracts | Exact underlying, expiry, strike and contract type; keep per-unit price separate from contract value and multiplier. |
| Other instruments | Identify the actual published price definition and unit before mapping it to the application. |

For every instrument retain the source URL, original price and unit, observed
date, meaningful price-basis label and supporting evidence. Normalize only when
the application contract supports the conversion, exactly once. If the adapter
cannot faithfully represent the observation, report **evidence found, saving
unsupported**, with the missing mapping. Never change a label, number or date to
make valid research fit an incompatible write schema.

## Application workflow

When the application asks to fill missing holding information, use its approved
enrichment REST tools and the request's existing budget. **Only open holdings
are eligible**, including open shorts and reopened positions. Fully closed
positions must be excluded before any model or source research; do not spend AI
calls on them. Private securities and employee option grants have no public
listing and are excluded from public research; never search internal grant IDs. Recheck eligibility before applying a result. This restriction
governs the application's missing-information action; an explicitly requested
historical research task can still concern a security no longer held.

The normal application refresh owns API-backed securities. They must not enter
the AI action, even if some fields remain missing or the provider has a temporary network/rate failure. Missing credentials require
provider configuration. Exact confirmed access/entitlement denial makes that API
unusable for current research; use AI public-source research if no other usable
API remains. This does not unlock the provider or permit bypassing its access
controls. Normal refresh can retry access and restore API ownership.
Only listings with no applicable API route, or exact verified unsupported
coverage with no alternative, enter AI research.

The dashboard exposes `search_security_sources`, `read_security_source` and
`follow_security_source` through authenticated, request-bound REST tools to both
CLI planners. Choose precise queries, inspect returned evidence, and follow
useful returned links within the remaining budget. Read an official
`source_hints` entry first when supplied: the server registers these discovery
leads without a network read; a hint still proves no price or identity. Read
only returned `source_id` values and follow only returned `link_id` values for
that security and request. Never invent IDs, URLs or additional tools.

Prefer selecting returned `context_records` with
`records:[{security_key,source_id,record_id}]`. The server recomputes the selected
record from its own fetched evidence and checks identity, date, raw unit,
currency and price basis before applying anything. A known source context may
connect a security header, quote card and date rather than requiring every
claim in one sentence. Conflicting fields and related-security widgets cannot
lend claims to the selected price. Unsupported contexts remain unknown;
search snippets and source hints alone never establish a fact. The authenticated
finalization endpoint alone saves supported missing values. It currently accepts
compatible raw Last/Close observations no older than
seven calendar days for this current-data action, plus literal sourced company
names and industries. The separate background/dashboard refresh applies official
fund redemption, compatible local U.S. bond marks and qualified fund/ETF closes
without a model. Unsupported
fundamentals, distributions or ambiguous conventions remain missing with a
friendly per-security outcome.
Do not report a fetched reference page as a completed portfolio update.

The dashboard uses `price_agent.reader: auto` (or `jina`) for key-free rendered
Jina Reader pages. Only public source URLs are sent to that external reader;
application credentials, portfolio records and browser sessions are not sent.
Choose `direct` for the application's HTTPS text reader instead. There is no
hidden reader fallback or retry. This adds rendered text and followable links,
not the interactive agent's proprietary search index or signed-in browser access.

One dashboard request shares at most **five model calls, five application REST
attempts and five public search/page requests** across all candidates. The REST
budget covers candidate reading, up to three research tool actions and
finalization. Failures count. Identical tool choices with identical arguments
can reuse a request-local response; a changed query, source or link is a new
choice. Repeated model decisions still count. Polling does not restart the run;
never split or rerun a limited request to reset its budget.

Read [the controller contract](references/controller-contract.md) for the
dashboard's context and reader rules or the separate host script's write schema
and stricter excerpt parser. These are implementation limits, not general
restrictions on researching prices.

### Host script updates

Run from the portfolio-analyzer repository root:

```bash
./.venv/bin/python scripts/update-security-prices.py --symbol AAPL --stock-market NASDAQ
```

For history, add `--date-from 01/10/2026 --date-to 31/10/2026`. Use `--dry-run`
for research or preview requests that do not authorize saving. `--ca-file PATH` supplies a
trusted CA certificate for the local HTTPS application. Never disable TLS
verification. Dates in the resulting API records use ISO storage format; report
dates to the user as `dd/mm/yyyy`.

Configuration lives in the existing `config.yaml` (or `CONFIG_PATH`; explicit
`--config PATH` overrides it). Read only the needed nonsecret fields. Use the
`price_agent` section with `provider: codex` (default) or `provider: claude`,
`model`, `reasoning_effort`, `max_model_calls`, `max_rest_calls`, `base_url`,
`timeout_seconds`, and `search: {provider: auto, api_key: "${BRAVE_SEARCH_API_KEY}"}`.
An empty model selects `gpt-6.1-sol` for Codex or the `sonnet` alias for Claude.
Medium effort is the default; low, medium and high are supported. The selected
CLI must be installed and signed in on the host. Search defaults to `auto`: use
Brave when its key is configured, otherwise public DuckDuckGo HTML results.
Explicit `brave` requires its key; `duckduckgo` is also selectable. A source block
or challenge is a temporary provider problem, not proof the price is unavailable.
There are no hidden provider retries or budget resets. Preserve existing YAML
sections and credentials.

Supply application authentication through `PORTFOLIO_API_TOKEN`, an existing
REST bearer token with write permission. Never include credentials in the model
prompt, command arguments, logs, screenshots or final response. If configuration
or permissions are missing, explain the prerequisite without inventing a result.
The security must already exist in the application with its exchange, currency,
location and asset class. Resolve ambiguous listings before updating.
Current-price requests reject observations older than the latest saved current
date; an explicitly requested history update can add older observations. Current
research reads a bounded daily item range while retaining the API's independent
latest-current result, then verifies only the submitted date range.

The controller enforces at most **five model calls and five application REST
calls per user request**, with a separate five-call internet-read ceiling.
Failures consume the same budgets. It disables native model tools and asks for
one decision per invocation, preventing nested autonomous loops. Do not rerun,
resume or split a failed/limited request to evade these ceilings. Review its
result and let the user initiate a separate request if necessary. Do not replace
the controller with an unconstrained Claude or Codex session.

Only evidence-backed finite positive prices may be submitted through this
application's updater. Search snippets alone are insufficient. Preserve original
source evidence and meaningful units; never invent values, infer a quote date
from retrieval time, confuse bond percent-of-par with cents, or splice raw and
adjusted history. Report remaining uncertainty: a successful textual match does
not prove that the chosen field is financially correct.

Report the security, exchange, observed dates, saved prices and units, cited
source URLs, outcome and call counts. A `written_unverified` result means the
write succeeded but verification did not; inspect existing saved records before
any later user-authorized retry. A failed write may have an unknown outcome and
must never be automatically repeated. A last-known saved observation is not
proof of a live quote. Keep missing evidence unknown.

This same skill is discoverable by Codex from `.agents/skills` and by Claude Code
through the repository's `.claude/skills/security-price-update` link.
