# Price research controller contracts

Use the matching section for dashboard missing-information research or an
automated update through `scripts/update-security-prices.py`. These are separate
implemented adapters with different tool and evidence contracts. Neither limits
general research to a fixed source list or a stock-specific lookup recipe.
Editing the skill guides agents invoking these adapters; it does not itself
change their prompts, tools, credentials or provider access.

## Host script

Inspect `app/price_agent.py` and `app/security_prices.py` if this adapter changes.
The host planner's prompt lives in `app/price_agent.py`.

The runner currently exposes `search_web`, `read_source` and `submit_prices` to
an isolated Codex or Claude Code planner. Search defaults to `auto`, selecting
Brave when a key exists and public Yahoo HTML otherwise; explicit `brave`
requires its key. A block/challenge differs from an empty search result;
source reads accept public HTTPS URLs returned by that request's search. Other
research channels described by the skill are available only when the calling
environment actually exposes them; the runner does not automatically acquire
browser, broker or provider tools by reading the skill.

The host research runner write schema supports **raw `last` and `close` prices only**. It does not yet
express fund NAV, unit value, purchase price or redemption price as distinct
bases. An Israeli fund can therefore have reliable research results that this
adapter cannot save. Preserve the real field label, report the adapter limitation
and leave the price unchanged; do not relabel NAV or redemption price as `close`
or bypass the controller through a different write route.

The API's listing metadata supplies `currency` and expected `quote_unit`. Under
the existing application model, Israeli inputs use agorot and US bond inputs use
cents, both normalized by dividing by 100; other supported inputs use currency
units. That is an application input contract, not proof of a webpage's scale.
The runner requires the raw source number in that expected unit: it currently
rejects mismatched units instead of converting the source quote. Find compatible
evidence within the remaining budget or report that conversion is unsupported.

Each proposed observation requires a fetched source identifying the security,
venue, currency and scaled unit where applicable. Its exact excerpt describes
one observed day adjacent to a matching Last/Close label. Adjusted values,
percentages, total-return data and unrelated event dates cannot establish a raw
observation. `observed_at` is null for date-only sources; a nonnull timestamp must
appear literally in ISO format with that observation. Retrieval time is recorded
separately by the controller.

The current parser accepts ISO dates, unambiguous day/month/year dates and English
named months. Ambiguous slash dates such as `11/06/2026` are rejected. Prices may
be integers or dot-decimal numbers, with either no grouping or valid thousands
groups such as `1,234.50`; comma decimals and malformed grouping are rejected.
These parser limits do not make otherwise valid source formats invalid financial
data. Do not rewrite the source excerpt to evade validation.

GET `/api/security/prices` supplies listing metadata, filtered observations and
an independent latest-current observation. PUT to that route saves a supported
batch, then GET verifies the submitted date interval. Current-price requests
reject source days older than the saved current day; explicit history requests
can fill older dates. Count failed calls against the shared per-request ceilings
of eight model calls, eight application REST attempts and eight internet reads.
Never reset or split the request to evade the ceilings or automatically retry a
write whose outcome is uncertain.

## Dashboard missing-information action

This is a separate application-controlled flow from the host script. Its
candidate REST route inventories open holdings with no applicable API route.
API-owned securities are excluded entirely when credentials are missing, a
provider has a temporary network/rate failure or other fields are incomplete.
A confirmed exact-identifier access denial permits AI public-source research
when no other usable API remains. Normal refresh retries configured denied
providers once within its existing bounded flow; recovery restores API ownership
and blocks late AI reads/writes. API prices
refresh through the normal background/dashboard flow. Closed positions never
reach the model. The model gets supported remaining gaps and the following
authenticated REST tools, with the same interface for isolated Codex and Claude
Code planners:

| Tool | Allowed choice |
| --- | --- |
| `search_security_sources` | A precise query retaining the candidate's identifier or name. Results are discovery leads, not evidence. |
| `read_security_source` | A `source_id` from the candidate's `source_hints` or this request's search. |
| `follow_security_source` | A `source_id` already read and one of that response's `link_id` values. |

Opaque source/link IDs belong to one request and security. The agent cannot
supply arbitrary URLs, native browser commands or HTTP requests. Public HTTPS
destinations and reported final URLs are validated; private/local destinations,
credentials in URLs and nonstandard ports are rejected. Source hints register
known official provider namespaces without fetching them. For example, eligible
numeric TASE ordinary-share IDs can receive an official security-page hint;
this is generic identifier routing, not verified data or a fixed security list.
Source hints and query hints are optional leads for Israeli and U.S. instruments,
not proof of availability, identity or correctness, and not a source constraint.
Choose useful leads for the actual instrument and missing fields, then adapt
discovery to the evidence. An industry-only gap does not require researching an
already-known price or name. `MANUAL` is not an exchange: a U.S. instrument keeps
its own identifier, type and source conventions even in a mixed-country batch.
Search in useful languages, refine a query, inspect a different source
or follow a relevant history/unit-definition link when budget remains. A blocked
search service is not an empty result; prefer an existing hint/discovered source
to repeating a blocked search. No automatic alternative-host search is hidden
inside an explicit tool action.

### Reader and privacy

The dashboard reads `price_agent.reader` from application-owned configuration.
`auto` and `jina` select key-free Jina Reader, which returns rendered Markdown
and followable links. Only the public source URL is sent; no portfolio payload,
application authentication, browser cookies, custom scripts or model extraction
instructions are forwarded. Image captioning, OCR and ReaderLM modes are not
enabled. `direct` selects the application's public HTTPS text reader, including
HTML links and bounded structured JSON where present. It rejects redirects.
There is no hidden fallback, retry or reader-provider switch. The host script
continues to use its separate `read_source` reader and excerpt contract above.

Rendered-reader responses preserve requested and reported final URLs, fetched
text/Markdown boundaries, retrieval time and returned links. A reader timestamp
never replaces the observation date. Rendering can still be blocked or omit a
field; it does not grant the interactive agent's proprietary search index or
signed-in browser state. One application request to the reader spends one public
read; the provider's internal asset requests are not observable or capped by this
application counter.

### Context selection and financial validation

A read can return `context_records` for supported price or profile fields.
The Codex and Claude Code bridges use the same research-specific output schema:
each decision has a nested `answer` object with required `records`,
`observations` and `profiles` arrays. Every record selection has exactly
`security_key`, `source_id` and `record_id`. Prefer those selections, using only
IDs actually returned. Unused arrays are empty, including on read decisions.
The final allowed turn retains this schema; it must not return chat prose or a
string containing JSON as `answer`. The bridge validates and serializes the
object into the controller's existing message-content JSON. The host script
continues to use its separate decision contract.

Finalization recomputes each selection from server-held
source evidence instead of trusting model-supplied prices, context claims or
IDs. It then revalidates listing, observed date, raw number, currency, unit and
basis, applies only supported missing values and preserves existing profile
values. Current prices must be within seven calendar days. An independently
qualified name or industry can be saved while an unsupported price stays unknown.

Context claims may belong to a main instrument header, quote card or supported
structured record; they need not repeat in one sentence. Contexts retain
literal field spans or explicitly labelled structured-data paths/raw values.
Known source-context failures cannot fall back to a looser excerpt check. For
unrecognized source formats, explicit `observations` and `profiles` JSON remains
available under the strict legacy evidence checks. Never rewrite source text to
make either path pass.

The implemented official Hebrew TASE ordinary-share context requires the exact
numeric listing/header, ordinary-share type, a Last label explicitly in agorot
and the main quote card's date. Both the security-root URL and its `major_data`
tab use this context; unrelated tabs cannot borrow its contract. That verified namespace uses `dd/mm/yyyy`;
date-only evidence has `observed_at: null`. Related/news widgets, market-cap
units and change amounts cannot supply price claims. Generic raw JSON contexts
require exact identity, venue, currency, raw unit, Last/Close and ISO date in the
same source object with literal field evidence. All explicit identity, currency,
unit, market and adjustment aliases must agree. Adjusted prices, NAV, yield,
coupon and percent-of-par are not silently relabelled as raw Last/Close.
TheMarker's stock context can qualify a name from exact namespace/asset metadata
and visible name evidence; it does not qualify a price whose unit is unknown.
These are implemented context contracts, not a source allowlist for research.

### Malformed-response recovery and diagnostics

A malformed final proposal remains a request error. Controlled planner budget or timeout interruption can likewise retain a missing final proposal and its original error. Application-owned
finalization may nevertheless recover a field whose server-recomputed fetched
contexts yield one unique, nonconflicting value. Recovery does not trust the
malformed text or cached model context claims. It passes the recovered
selections through the same source validator and repeats current missing-field,
open-holding and API-ownership checks before saving. Conflicting or unsupported
fields stay missing. Recovery adds no model, REST or public-source call and
does not hide the parser failure or mark untouched securities as researched.

For a missing proposal, deterministic recovery is enabled only by the server-owned request_limit or planner_timeout reason. Authorization expiry, cancellation and a valid empty proposal never enable it. Existing eligibility and API ownership checks still apply.

The authenticated finalization route records a bounded trace of model
requests/responses and tool choices/results in redacted application diagnostics,
correlated by request ID. Existing diagnostic redaction protects credentials;
the runtime planner receives no filesystem or log-store access. A trace enables
comparison of the actual query, page, context and final decision with the
reviewing agent's path; endpoint HTTP success alone does not prove an accepted
fact or completed save.

### Shared budgets and response reuse

The whole click shares at most eight model calls, eight application REST attempts
(candidate read, up to six search/read/follow actions, finalization), and eight
application-owned public search/page requests across all candidates. Defaults
and hard ceilings are eight; lower configured limits remain effective. Failed
attempts count. Up to three selected candidates is an inventory limit, not a
promise that each will be researched: one source may use multiple actions.
The planners have no native tools, shell, filesystem, database,
generic HTTP or other-agent access. Source evidence belongs to the request and
security. No AI-eligible open candidates avoids model invocation. An unfinished
batch requires a new user action; polling job status never restarts research or
resets counters.

Response caches use the tool/action and full validated arguments, including
security key, query, source ID and link ID as applicable. An identical choice can
reuse a returned response without another REST/upstream attempt; changing any
argument is a new choice. Each model decision still counts. Failed HTTP attempts
consume their budgets and are not cached as successful reads; a returned
unavailable result can be reused without repeating its upstream attempt.
Untouched securities, including a source request rejected before any upstream
read, remain not attempted. A later request-level failure does not overwrite the
reason already recorded for a researched security.

## API-first price application

The normal background refresh retrieves supported public API observations; this
flow is separate from the AI action and requires no model or search key. `GET
/api/security/israeli-fund?fund_id=...` returns exact-fund MAYA current and
historical purchase/redemption observations, source dates, units and partial
coverage. The fund number is generic, not a fixed list. Domestic ordinary ILS
fund prices are quoted in agorot per issued unit; divide by 100 exactly once,
without multiplying by a fund's nominal value. Foreign, deleted or ambiguous
fund profiles remain unqualified. Redemption is the declared held-fund price
policy; purchase prices remain distinct.

For locally recorded U.S. bonds with exact CUSIP/ISIN, primary asset class BOND,
USA location and USD currency, the established local convention is USD 1 face
per recorded unit. Raw API percent-of-par P passes through the same price input
as manual entry and normalizes to P/100. Preserve official daily valuation, or
the actual Treasury programme redemption bid for a long/purchase mean for a
short when daily valuation is absent; an available opposite-side mark remains
labelled with its actual basis. These are reference valuation marks, not an
executable broker quote. Imported, foreign-currency or subclass-only instrument
conventions require a compatible mapping; never infer it from registration.

Normal provider workers stage verified observations in application-owned caches.
A bounded application coordinator alone applies automatic price rows, rechecking
open/public holdings, current metadata and known units immediately before saving.
Timed-out or cancelled work may finish caching source evidence but cannot perform
late price writes. All open API listings are considered, without the AI batch's
three-security limit. Transient API failures stay in the API flow; confirmed
access denial can release AI eligibility. Exact unsupported
coverage is cached separately and can make a listing AI-eligible; a generic
transport error cannot. Compatibility alone is not proof of exact source coverage.
Existing dated prices are preserved; current evidence must be within seven
calendar days. Past-maturity source history stays historical; no current quote,
par payment or cash receipt is invented. Compatible U.S. fund/ETF closes in
currency per share retain their raw amount, without a divide-by-100 conversion
or NAV relabelling. Finnhub requires configured provider access, `quote_unit`
and source or explicit `quote_currency`; actual units/currency keep their origin.
Saving API observations spends no model calls. Source/provider
reads are bounded separately; the agent's total remains eight model requests and
eight authenticated application REST attempts, including failures. The runtime
agent still has **no database, filesystem, shell or generic HTTP access**.
