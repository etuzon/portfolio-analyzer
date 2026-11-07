# Current controller contract

Use this reference when sending an automated price update through
`scripts/update-security-prices.py`. Inspect `app/price_agent.py` and
`app/security_prices.py` if behavior changes; this reference describes the
implemented adapter rather than limiting general price research.
The automated planner's prompt lives in `app/price_agent.py`; editing the skill
guides agents invoking it but does not itself change that prompt or its tools.

The runner currently exposes `search_web`, `read_source` and `submit_prices` to
an isolated Codex or Claude Code planner. Search defaults to `auto`, selecting
Brave when a key exists and public DuckDuckGo HTML otherwise; explicit `brave`
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
of five model calls, five application REST attempts and five internet reads.
Never reset or split the request to evade the ceilings or automatically retry a
write whose outcome is uncertain.

## Dashboard missing-information action

This is a separate application-controlled flow from the host script. Its
candidate REST route inventories open holdings and first tries the ordinary
providers. Closed positions never reach the model. The model gets only remaining
gaps, a request-bound `fetch_security_information` REST tool, and fetched public
evidence; it has no native tools or storage access. It returns proposed
observations and profile fields as JSON. The authenticated finalization route
validates exact listing/source/date/number/unit matches and applies supported
missing values, preserving existing profile values. Each current price must be
no older than seven calendar days. Company name and industry proposals require
literal labeled evidence; unsupported fields remain unknown.

The whole click shares at most five model calls, five application REST attempts
(candidate read, up to three source reads, finalization), and five upstream
search/page reads. Failed attempts count. Source evidence belongs to that
request and security. No configured search, no open candidates, or an API-only
resolution avoids model invocation. An unfinished batch requires a new user
action; polling job status never restarts the agent or its budget.

## API-first price application

The dashboard action first retrieves supported public API observations; this
phase does not require a model or an Internet-search key. `GET
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

Preflight reads stage verified observations in application-owned provider caches.
The authorized finalization POST alone writes eligible missing local price rows,
rechecking open/public holdings and known units immediately before saving.
Existing dated prices are preserved; current evidence must be within seven
calendar days. Saving API observations spends no model calls. Source/provider
reads are bounded separately; the agent's total remains five model requests and
five authenticated application REST attempts, including failures. The runtime
agent still has **no database, filesystem, shell or generic HTTP access**.
