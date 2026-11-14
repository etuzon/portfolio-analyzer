# Shared portfolio risk: portfolio-risk-v3

The current dashboard, industry/holding/account badges, trade planner, simulator
and risk-reduction alternatives use `web/stress-risk.js` through the wrappers in
`web/app.js`. This is severe modeled capital-loss **severity**, not a probability,
VaR, expected shortfall, forecast, broker margin rule or exhaustive maximum loss.
Company-outlook scores and personal suitability remain separate.

For positive net equity `E = signed securities + signed account cash`, calculate
each common scenario's signed base-currency P&L, then
`round(min(100, 200 * max(0, largest modeled loss) / E))`. Score 60 means a 30%
modeled loss; keep uncapped loss amount/percent visible above the display cap.
Known nonpositive equity with securities/debt scores 100; debt-only scores 100;
known empty debt-free portfolios score 0. Unknown valuations/cash/FX never imply
insolvency or zero risk. Positive cash dilutes market exposure; borrowing reduces
equity and remains separately summed by account even when consolidated cash is
positive. There is no ten-component sum, excess/insufficient cash penalty,
horizon penalty, borrowing-point multiplier or 75/25 account blend in v3.

## Scenario and instrument contract

All shocks below are explicit analyst assumptions, not calibrated probabilities.
Broad agency buckets AAA/AA/A/BBB/BB/B/CCC use spread widening
50/75/100/150/300/500/800 basis points. Recession is equities -40%, separate
benchmark curve -100bp, credit widening x1; inflation/rates-up is equities -25%,
curve +200bp, widening x0.5; rally is equities +40%, curve -200bp, spread tightening
by the smaller of the bucket amount and the supplied current spread. Every
global scenario and an FX-only case uses fixed FX, all foreign +/-15%, and each
foreign currency +/-15%. Reprice local first, then compound
`(1+local return)*(1+FX return)-1`. Apply FX to signed foreign cash/debt too.

Aggregate the same legal issuer across lots/symbols/accounts. Corporate issuer
equities have separate -60% distress and +100% rally cases. Corporate debt
distress spread is `max(0.2/D, 2*bucket widening)` where `D` is the model's
positive-cashflow continuous-yield PV-weighted duration, equal to maturity time
for a confirmed zero coupon. Issuer rally uses curve -200bp and credit tightening
to zero. Direct sovereigns never receive this corporate issuer-distress channel.

Country crisis assumptions by AAA/AA/A/BBB/BB/B/CCC are respectively: local equity
-35/-35/-40/-45/-55/-65/-75%; sovereign widening 100/150/200/300/500/800/1200bp;
country currency -10/-10/-15/-20/-25/-35/-50%. Use documented economic exposure
or explicitly labelled domicile proxies, never account custody location or
listing currency as issuer identity. Corporate country spread is the maximum
of its own ordinary widening and explicit sensitivity `kappa * country widening`,
not their sum. Government credit uses the eligible exact sovereign issue opinion first, or that
obligation's matched sovereign local-/foreign-currency issuer fallback, without merging those axes across positions.
Country-currency shock uses the separate foreign-currency systemic opinion when
that non-base currency has modeled exposure or cash; missing relevant FC evidence
leaves the total incomplete. Base currency never moves against itself.

Supported bond repricers are confirmed plain nominal noncallable zero coupons
(`exp(-T*delta_yield)-1`) and supplied complete future cashflows discounted at an
explicit current flat continuously compounded yield. ACT/365.25 rolls maturity
and payment times from the frozen as-of date. Zero coupons do not need baseline
yield for the return ratio. Coupon bonds require current continuous yield and
the full future schedule. Maturity is never substituted for coupon-bond duration.
Current credit spread is needed for rallies. Do not apply a spread again when
an all-in yield shock already includes it. Callable, floating, inflation-linked,
convertible or nonlinear instruments remain unsupported without a suitable model.

## Evidence, estimates and scope

`app/stress_risk_inputs.py` attaches cache-only, identity-bound inputs to fresh
portfolio, planner, simulator and captured history/scenario contexts. Admin and
Operator can edit/clear dated local inputs in Security overview → Risk inputs;
Viewer can read. Writes never reach an external import source. Revision/identity
checks reject concurrent stale edits, and source changes invalidate derived risk
without forcing market-data refetches.

Use matched current verified global long-term issue ratings first, or an explicit
matched issuer fallback. Sovereign LC/FC follows the obligation relative to its
issuer, independently of investor base currency. National, short-term, stale,
withdrawn, conflicting and default-ambiguous opinions do not become comparable
ratings. Choose the weakest **comparable** eligible agency opinion. Manual
effective overrides block strict scores; enabling explicit assumption mode may
use them for `estimated_score`, with provenance, never as verified agency facts.
Negative outlook/watch creates a separate one-broad-bucket downgrade sensitivity;
stored grades stay unchanged and both signals do not count twice.

`score` is null for missing required inputs. Known partial scenario results and
value-weighted input coverage remain separate. Explicit permitted assumptions
return `status=estimate`, `score=null`, and `estimated_score`; UI displays `~`
and a visible estimate label. User-entered risk parameters and economic/domicile
proxies retain their confidence distinction. Saved valuations and current bond spread/yield observations older than seven
calendar days cannot establish a complete current score; saving an old source
observation does not refresh its as-of date. Static classification or cashflow
terms do not expire solely because their source is old. Cash's zero nominal
market stress is not a guarantee of deposit protection, access or purchasing power.

Funds require actual/declared underlying issuer, credit, country, rate and FX
exposures. The pure engine can evaluate supplied complete look-through and rejects
inconsistent wrapper/child currency hedges. The current backend/editor does not
provide a fund look-through entry workflow; actual funds without that evidence
remain incomplete. An ETF label, fund-manager rating or asset-focus profile never
establishes underlying credit or diversification. Savings balances lacking
allocations stay outside securities/cash risk; do not call this whole-wealth risk.

Intrinsic holding risk is unlevered standalone unit exposure, independent of
actual size, lot representation and account borrowing. Actual signed portfolio
contribution is P&L under the identified pooled worst scenario; hedges may have
negative loss contributions. Funding, deposit/custody access, default contingencies
without verified recovery, and personal investment horizon are separate issues.

## Versioned history and simulations

New observed records carry v3, score/estimate/incomplete status, input/rating
evidence, source revision, assumptions and actual captured FX. Old v2 observations
remain immutable and retain their heuristic explanations. History does not connect
lines across model versions or estimate statuses and never plots a null as zero.
Observed days are not retrospectively backfilled. Scenarios use their coherent
captured as-of date, parameters, prices and FX; later live updates do not rewrite
them. New calculations capture current evidence. Simulation totals retain their
Investment-account scope; risk-reduction alternatives retain canonical dashboard
scope. Source corrections, rating/parameter/country changes and provider evidence
enter the capture/publication guard.

Regression evidence includes `tests/test_stress_risk_model.py`,
`tests/test_stress_risk_inputs.py`, independent financial/QA tests, simulator,
history, source-revision and browser/localization checks. Software tests do not
validate financial forecast accuracy.

## Historical v2 contract (immutable observations only)

Previously implemented by `riskScoreForItems` and `portfolioRiskSnapshot`.
Stored v2 observations used the following rule. This was a heuristic, not calibrated loss
probability or broker margin eligibility. Company-outlook scoring is separate.

All monetary inputs to the risk function use one base currency. Let signed cash
be `N`, total borrowing be `D = max(0, -N, supplied_account_debt)`, positive cash
assets be `P = max(0, N + D)`, and net equity be signed securities value plus `N`.
Aggregates supply `supplied_account_debt = sum(max(0, -account_cash))`; cash in
other accounts must not erase an account's borrowing.

The existing ten component weights stay unchanged: concentration 16, asset mix
14, currency 10, industry 10, cash buffer 7, derivatives 10, volatility 10, horizon
10, issuer/country 8, data quality 5. Compute their unrounded sum `S` using gross
security exposure plus positive cash assets `P`. The cash-buffer rule remains
zero points at 5–20% cash, increasing below that range, and a capped excess-cash
penalty above it.

For positive net equity `E`, add `min(100-S, S*D/E)` borrowing points, then round
and cap the final sum to 0–100. With securities exposure or borrowing and `E<=0`,
score 100. Empty zero-value, debt-free portfolios score 0. A debt-only account
also scores 100. Holding-risk estimates apply the same borrowing multiplier.
Never replace an otherwise calculable risk score with a cash-deficit label.

Account rollup weights are gross securities value plus positive account cash,
so they stay nonnegative. Total risk is 75% combined score plus 25% weighted
account score; nonpositive combined equity with exposure/debt overrides it to
100. Industry comparisons allocate signed cash and borrowing by industry value.
Simulation totals include only Investment accounts; dashboard scope is unchanged.

Show modeled borrowing separately, including its sum across accounts even when
combined cash is positive. Risk tooltips explain the borrowing adjustment and
debt/equity ratio. True missing prices, currency, classification or FX still make
the simulator's affected risk unavailable; do not invent data to force a score.

Regression coverage: `tests/test_shared_cash_risk_qa.py`, simulator financial and
Investment-scope tests, frontend Help/localization tests. Exercise positive,
zero and negative cash, debt-only and nonpositive-equity cases, offsetting cash,
FX, account/total dashboard parity, frozen snapshots and source immutability.

[SEC margin guidance](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-29)
supports the general borrowing-risk rationale; it does not endorse this app's
scoring formula or weights.

### Historical v2 observed risk history

Risk history keeps `portfolio-risk-v2` unchanged. It records browser-calculated
assessments from coherent server contexts, tagged `dashboard_client_calculated`.
Canonical scope excludes ESOP/equity compensation and ignores transient holdings
filters. Account IDs, model, base currency, component/gap details, actual saved FX
and source revision are frozen. Saved FX can differ from newer live badge FX.
Existing value/cash account snapshots do not support retrospective risk backfill.

Capture requires a finished source, known required valuations/quantities/cash and
positive conversion FX; deliberate data-quality penalties remain recordable.
Generation, source signature and saved FX are rechecked at publication. Risk
history preferences are excluded from the financial change token. Historical
observations remain immutable after corrections. Charts show the last observation
per Jerusalem day, with gaps for unobserved days and a dot for a single point.
A missing-data score is weighted points, with serializable contributor details;
it is not a count of absent records. See `tests/test_risk_history.py`, frontend
history/independent QA and risk-data-gap tests.

### Historical v2 risk-reduction alternatives

The dashboard's Explore lower risk tool uses `web/risk-scenarios.js` and the
read-only `/api/portfolio/risk-scenarios/context` capture. Unlike the separate
Trade Simulation tool's Investment-only total, these comparisons retain the full
canonical dashboard scope, including unchanged Bank and Long-Term Savings
accounts and excluding employee equity. The account selector filters sale
candidates, never the total denominator or cash.

Each alternative independently projects one supported long sale from the same
frozen source. Generate at most the user's configured 1–20 scenarios (default 5),
choosing measured qualifying partial sales among 10%, 25%, 50%. Neither account nor
total score may increase and at least one must decline for an initial suggestion.
Interactive amounts may range 0–100% and must recalculate the exact model, retain
nonqualifying edited cards, and never interpolate scores or combine alternatives.

Use coherent saved prices/FX and the existing dashboard model through
`riskHistoryCalculate`; disclose that captured saved-FX baselines can differ from
live badges. Preserve unknown cash, valuations, classification and FX; reject
future activity. Require quantity times dated saved unit price to match valuation.
Sale proceeds enter the same account. Cross-currency proceeds require an explicit
opt-in assumption to convert at the captured source/base divided by account/base
rate, preserving base equity. Quotes stay fixed; fees, taxes, interest, slippage
and reinvestment are excluded. This tool places no trades and changes no ledger.
