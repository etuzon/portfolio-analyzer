---
name: us-bond-fund-data
description: Retrieve prices, price history and reference data for U.S. bonds, mutual funds and ETFs by CUSIP, ISIN or ticker through portfolio-analyzer REST or suitable financial sources. Use when an application or user needs security data, not trade execution or forecasts.
---

# U.S. bond and fund data

## Mandatory data-access boundary

**The AI agent must NEVER read or write a database. It obtains all application
information and performs any authorized changes only through explicitly allowed,
authenticated and authorized REST endpoints.** No SQL, ORM, SQLite/PostgreSQL
client, database file, backup, export or shell helper may bypass this boundary.
Never obtain database credentials or expose a generic SQL/HTTP execution tool.
If the allowed REST tools lack a capability, report that limitation.

Use the initiating user's permissions, not a privileged service account. Enforce
role and token authorization in addition to authentication; read-only users and
tokens cannot perform updates. Browser actions retain CSRF protection. Keep
credentials out of model prompts, user output and logs. The application owns
internal persistence; that does not grant the agent database access. Source
research must also use only capabilities actually exposed by the environment;
application-triggered agents receive only approved REST tools.

Resolve the requested instrument and data rather than relying on a remembered
quote. This guidance covers U.S. bonds and funds generally; example identifiers
are illustrative and are not an allowlist. Adapt the source and research method
to the instrument, available tools and requested time range.

## Application requests

Prefer `get_security_market_data` when exposed by the application, or the
authenticated REST endpoint `GET /api/security/market-data`. Supply `identifier`
and `kind` (`bond`, `fund` or `etf`); optional fields include `identifier_type`,
`provider`, `date_from`, `date_to`, `cache_only` and `refresh`. This fetches and
caches data automatically; the caller supplies an identifier, not manually
entered prices. It does not create securities, transactions or local valuation
overrides. The application may research an instrument it does not yet hold.

Locally registered bonds without a stock ticker can still have an automatic
bond feed. Do not infer unavailable market data from a `MANUAL` registration
origin. The security-history response can include a separate `market_data`
snapshot containing API reference observations and terms; check its provider,
dates, quote unit and coverage. A price per $100 face must stay separate from
the portfolio's currency-per-quantity-unit prices until the quantity/par mapping
is explicit. Source programme purchase/redemption values are not generic
exchange closes. Mixed historical bases need labels or separate series.

Examples, using the same endpoint for different instruments:

```text
/api/security/market-data?identifier=91282CKD2&kind=bond
/api/security/market-data?identifier=037833DV9&identifier_type=cusip&kind=bond
/api/security/market-data?identifier=SWPPX&kind=fund&date_from=01/01/2025&date_to=31/12/2025
/api/security/market-data?identifier=VTI&kind=etf
```

Automatic provider choice uses configured Finnhub access for bonds, with public
TreasuryDirect coverage for Treasury securities; funds/ETFs use configured EODHD
access. Explicit provider selection is available. Coverage, entitlements and
history depth vary: a generic request format does not guarantee every security
has data at every provider. Respect returned configuration, coverage and error
statuses instead of substituting a similar instrument or manufacturing values.

Read `coverage`, `latest_in_range`, `quote`, observation dates, source fields and
cache status. A historical result does not establish today's quote; current
profile or fund-holdings data accompanying it is not a historical point-in-time
profile. Public Treasury history can be partial because daily requests are
bounded; follow its continuation date only within the remaining shared request
budget. `cache_only` avoids provider access; a failed refresh can return retained
evidence marked stale. Do not call indefinitely to complete a large history.

Keep credentials in the requesting client's authentication and server-side YAML
provider settings, never model prompts or source URLs. The existing per-request
limits remain at most five model exchanges and five application REST attempts,
including failed attempts. Each fetch also has at most five upstream provider
attempts. Do not reset, split or nest requests to evade those ceilings.

## Bonds

Search by the complete CUSIP or ISIN, and confirm issuer, coupon, maturity and
currency. Government notes, bills, TIPS, floating-rate notes, corporate bonds and
other debt have different terms. Bonds commonly trade through dealers rather
than an equity exchange; a CUSIP is an identifier, not a stock ticker. Match the
actual security instead of using a Treasury yield-curve tenor as its price.

TreasuryDirect offering/auction records are useful for Treasury terms and
issuance facts. Their auction price is not a later secondary-market price.
Official FedInvest daily pricing, appropriately licensed bond feeds, broker
research and reputable quote sources are alternative price evidence, depending
on availability. Discover actual documented endpoints or published records;
these examples do not restrict other valid sources. Finnhub, for example,
documents bond profiles by CUSIP/ISIN and historical prices by resolved ISIN.

Keep the price unit and field meaning explicit. A decimal quote of `99.354` per
100 face is percent of par, not 99.354 cents. Fractional Treasury quotations may
use 32nds. Distinguish clean price, accrued interest and dirty settlement price,
and preserve the applicable valuation/settlement date. Keep coupon, current
yield, YTM and yield-to-worst separate. Do not calculate a missing price from a
yield unless a valuation calculation was actually requested with sufficient
terms and assumptions.

Provider-specific sides also matter: FedInvest programme purchase/mean and
redemption/bid fields must retain their definitions, rather than being renamed
generic market bid/ask. Missing or placeholder end-of-day values cannot be
replaced by an auction price. Unknown price basis or currency stays unknown.

Preserve useful reference data when available: issue/maturity dates, coupon and
payment schedule, day-count convention, callable/puttable terms, issuer and
currency. Ratings and provider-calculated risk or yield analytics need their own
source dates and definitions. Missing data is not zero.

## Funds and ETFs

Resolve the exact ticker or ISIN and share class. Check the fund family, currency,
domicile and instrument type. For mutual funds, distinguish dated NAV/unit value
from an independently traded price. For ETFs, market price and NAV are separate
observations. A provider's field called `close` is not sufficient proof of NAV.

Issuer documents, approved data providers, broker research and reputable fund
portals can provide evidence. Retrieve actual dated history from tables,
downloads or documented APIs, and inspect response coverage and pagination.
Keep raw close, adjusted close and total-return series distinct; a performance
chart rebased to 100 does not supply unit prices. Fund size and percentage
returns also do not establish a current share price.

Other useful data may include fees, distributions, benchmark, holdings,
allocations, fund family, inception and assets. Retain each dataset's update date
and share class; today's holdings must not be described as historical holdings.

## Applying results

For application-triggered missing-information updates, research only open
holdings after the application's normal API attempt. Open shorts and reopened
positions qualify; fully closed holdings do not consume model or research calls.
Use the approved request-scoped enrichment tools without restarting or splitting
the five-model/five-REST budget. Eligibility is checked again before saving.
This restriction does not prevent explicitly requested historical research for
other instruments through the read-only market-data endpoint.

Research and provider caching do not authorize portfolio changes. In particular,
bond positions may measure quantity in dollars of face or in lots of another
size. Do not revalue them from a percent-of-par quote until the quantity/par
mapping is explicit. If an authorized save is requested, use the application's
supported price workflow and preserve the real basis and units. If the current
adapter cannot represent the observation, report the evidence and the missing
mapping rather than relabelling it or asking the user to type a guessed price.

Report the instrument, observed date, value and unit, meaningful price basis,
source and retrieval/coverage status. Distinguish retrieved facts from provider
calculations and unverified fields. Never claim a live executable quote or a
completed portfolio update from a cached research response.

## Applying supported local bond prices

The normal background refresh connects verified API evidence to the same
application price input used for manual entry, separately from AI research.
API-owned securities never enter the AI
inventory; unavailable credentials or temporary provider failures remain API
configuration/refresh problems. Exact unsupported coverage with no alternative
may allow AI research. Eligible local USA/USD/BOND
CUSIP or ISIN positions use USD 1 face per recorded unit: P per100 normalizes
once to P/100. Keep the real source valuation or Treasury programme side; never
rename a programme purchase/redemption mark as an exchange close. Existing dated
observations and closed positions are preserved. Source-imported quantities,
foreign currencies and subclass-only classifications do not establish this
local convention; retrieve reference data without guessing a conversion.
Automatic publication and storage belong to application business logic, never
the AI agent. Successful API-only results require no model request. Matured
securities can still have actual price history, but do not manufacture a current
price or assume redemption cash. API subscription/category support does not
prove that a particular agency strip or corporate identifier has live coverage.
