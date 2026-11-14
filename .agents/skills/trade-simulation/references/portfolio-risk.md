# Shared portfolio stress loss: portfolio-risk-v4

The current dashboard, industry/holding/account badges, trade planner, simulator
and risk-reduction alternatives use `web/stress-risk.js` through the wrappers in
`web/app.js`. The current measure is **stress capital-loss percent** under fixed
hypothetical scenarios, not a probability,
VaR, expected shortfall, forecast, broker margin rule or exhaustive maximum loss.
Company-outlook scores and personal suitability remain separate.

For positive net equity `E = signed securities + signed account cash`, calculate
each common scenario's signed base-currency P&L. Let
`L = max(0, max_s(-pooled_P&L_s))`, then `loss_pct = 100 * L / E` and
`score = round(min(100, loss_pct))`. The factor 100 converts a fraction to percent;
it is not empirical calibration. The underlying economic result is the unrounded,
uncapped `loss_pct`; `score` is its rounded capped representation. Recompute
from money P&L and equity, never halve a previously rounded v3 score. Dashboard
badges and the current history chart display **Stress-loss score / ציון הפסד
בתרחיש קיצון** as the rounded 0–100 number. Display the uncapped loss percentage
beside/below it and retain it in history tables and accessible explanations.
Use two decimal places, increasing precision for tiny positive losses so a zero
rounded score never implies no loss. For example 36.47% gives score 36. Simulator
and planning percentage surfaces retain explicit `%` units. Do not introduce
uncalibrated Low/Moderate/Elevated/High/Extreme bands. Preserve monetary loss and
percentages above 100%; the display cap must not hide losses exceeding net equity.
For v4 compatibility rounding only, allow a `1e-10` percentage-point tie tolerance
before rounding the clamped percentage. This removes binary floating-point
misrounding such as mathematical 44.5 represented as 44.49999999999999. Use the
same tolerance in the v4 history validator. Raw money, loss percentages and
financial policy comparisons remain unrounded; historical v3 rounding is unchanged.

New assessments carry `score_unit=percent_capital_loss`,
`score_scale=stress-loss-percent-v1` and
`scenario_horizon=instantaneous_revaluation`. These shocks instantly reprice the
captured positions; they have no event timing, annual holding period, confidence
level, or occurrence probability. A benchmark-normalized score or statistical
VaR/volatility measure requires a separate justified method and validation;
do not choose a scale merely to produce desired benchmark rankings.

Known current nonpositive equity with securities/debt retains score 100 only as
a funding-boundary sentinel; debt-only does likewise. Keep `loss_pct=null`, a
separate `nonpositive_equity` reason and visible nonpositive-equity language;
never present that sentinel as a measured 100% loss or whole-wealth insolvency.
Known empty debt-free portfolios score 0. Unknown valuations/cash/FX never imply
insolvency or zero risk. Positive cash dilutes market exposure; borrowing reduces
equity and remains separately summed by account even when consolidated cash is
positive. There is no ten-component sum, excess/insufficient cash penalty,
horizon penalty, borrowing-point multiplier or 75/25 account blend in v4.

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

Public evidence can introduce an exact SEC issuer ID while another listing
still has a previously verified legal-name identity. `issuer_name_key` normalizes
only those verified legal names, retaining parent/bank/holdings tokens. The
calculation builds an alias registry from all captured verified identity facts,
including positions missing other model inputs. A unique SEC ID for that exact
legal name also identifies matching verified-name fallback positions; raw source
IDs/names remain unchanged in the frozen inputs. Identifier formatting or partial
research coverage must not create diversification. Verified name-only formats
`<name>` and `issuer:<name>` share the same legal-name grouping when no stronger
bound identity is available. Multiple distinct strong IDs
or contradictory known legal jurisdictions leave weak name-only mappings
incomplete/provisional. Unverified, fuzzy, display-name, account-country and
exchange-based joins are forbidden; separately proved strong identities remain
distinct. Fully modeled coverage is recomputed after late shared country/FX and
identity checks, excluding affected positions and foreign cash consistently.

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

### Asset-aware estimates with incomplete evidence

The automatic overlay is `portfolio-risk-provisional-v3`, with
`provisional_basis=asset_aware_scenarios`. It leaves the strict v4 `score`,
`status`, ratings and raw facts unchanged. Display precedence is a verified
score, then a complete explicit-assumption `estimated_score`, then an automatic
estimate. Incomplete estimates display `~N`, a warning and a localized Estimate
label. Strict boundary scores with remaining gaps also retain the warning.
Tooltips retain every missing input, value-weighted coverage, source dates and
explicit proxy assumptions. Completeness adds no loss or score points.

Automatic estimates use the same signed common-scenario P&L, positive-equity
denominator and `round(min(100, 100 * loss / E))` compatibility scale as strict
v4. A fully scoped estimate also supplies unrounded, uncapped
`provisional_loss_pct=100*provisional_loss/provisional_net_equity`. With incomplete
scope that field stays null; a separate `provisional_known_loss_pct` may describe
supported known positions with a positive estimated denominator, clearly as a
secondary result. It is not the whole portfolio or a verified loss bound.
Known cash has zero local price shock, dilutes exposure and retains signed FX
shocks; borrowing reduces equity. Fund classification requires an explicit
instrument/profile classification, not a name, broker, listing currency or a
fund's numeric ID. A direct share/RSU retains issuer distress even when an
incompatible fund-focus profile is attached. Unknown raw classification with an
explicit equity kind can use the share proxy. Unsupported derivatives, leverage
or known nonplain bonds require a suitable model and cannot become ordinary debt.

For funds without verified complete lookthrough, use the declared category:

| Exposure | Local proxy assumptions |
|---|---|
| Unleveraged money-market fund | -1% NAV in recession/inflation; zero in rally; country loss at least 1%, or 25% of the eligible country spread shock |
| Government bond / government bond fund | Duration 5 years; unknown credit widening 200bp |
| Corporate / unspecified direct bond or bond fund | Duration 5 years; unknown widening 250bp |
| Investment-grade bond fund | Duration 5 years; widening 150bp |
| High-yield bond fund | Duration 4 years; widening 500bp |
| Direct equity or broad/unclassified equity fund | Global -40% recession, -25% inflation, +40% rally |
| Declared sector/thematic equity fund | Global -50% recession, -35% inflation, +50% rally |

Canonical `MONEY_MARKET_FUND` and `BOND_FUND` class/subclass aliases use their
respective category even without a separate focus. A broad single-country fund
does not receive the sector proxy merely for being single-country. Eligible
direct-bond credit and actual confirmed zero/coupon terms take precedence over
proxies. A no-lookthrough fund never inherits its manager/wrapper issuer rating,
maturity, cashflows, country sensitivity or current credit spread as underlying
bond evidence; retain category duration/widening and sensitivity1. No corporate issuer-default shock is assigned to
a fund manager. Verified lookthrough children use their actual direct-instrument
rules, including canonical legal-issuer aggregation across flat/nested children.

Proxy bonds use `expm1(-D * (curve + spread))`; retain the global curve and spread
multipliers above. If no eligible current credit spread is supplied, omit credit
tightening from rallies and label that omission; do not claim an observed zero
spread. Direct corporate issuer distress/rally stays applicable with the proxy
duration. Eligible matched sovereign issue/LC/FC opinions retain their axes.
The automatic estimate may use an existing exact TreasuryDirect reference in
`item.market_data` to recognize plain USD Treasury bills/notes/bonds as sovereign
US/USD local-currency obligations. Require an exact bound CUSIP, USD currency,
Treasury issuer, an HTTPS TreasuryDirect primary source and a nonfuture reference
capture. Identity establishes the sovereign category independently of missing
pricing terms. Missing nominal flags/type retain a labelled sovereign D5/200bp
proxy without a maturity bound. Explicit floating, inflation-linked, callable or
contradictory nonlinear terms instead require a suitable payoff model and range.
Partial price/history coverage does not invalidate supported static identity.
This adds no sovereign grade, current yield or spread, and a coupon note is not
a zero coupon. A known matured reference requires an appropriate payoff model.
If an exact repricer remains unavailable, verified nonfloating/non-inflation-linked
plain nominal type and final maturity may cap
the default duration proxy at remaining ACT/365.25 years. Label this
`bond_duration_maturity_bound` with its maturity and source: it is a conservative
sensitivity proxy, not actual coupon duration. User-entered maturity alone,
including enabled manual assumptions, does not establish this verified bound.
Keep reference retrieval dates distinct from quote observation dates. These
reference aids leave strict v4 completeness requirements unchanged and perform
no network lookup or data write while calculating risk.
For direct securities, an explicitly labelled issuer-domicile proxy may support
country scenarios. A fund's manager domicile does not establish its underlying
economic country. Without declared underlying economic-country evidence and an
eligible rating, use generic country equity -40%, spread +200bp and currency -15%.
Retain eligible direct-security country sensitivity, or label `kappa=1` as an
assumption. User-entered parameters require explicit assumption mode; an
unenabled manual sensitivity0 cannot suppress a known country shock.
Generic country, domicile and quote/reference-currency fallbacks are labelled.
Declared economic FX weights take precedence; otherwise label a quote/reference
currency proxy. Compound all local/FX returns and apply FX to signed cash too.

Finite reported saved values may support a last-known estimate when valuation
dates are stale or absent, with dates/assumptions visible. Future-dated values are
excluded. Missing monetary values, conversion FX, cash, supported exposure or
pricing models set `provisional_scope=known_values` and display Incomplete,
never a forced 100 or an arbitrary midpoint. Any stored 0–100
`provisional_range` describes the capped compatibility index, not an economic
loss-percent bound: borrowing and shorts can lose more than net equity. A secondary
point may describe supported known positions only; it is not the whole-portfolio
score and is not plotted as one. With fully scoped values/exposures, use
`provisional_scope=portfolio`. Known current nonpositive equity retains the
funding boundary with null loss percentage; stale nonpositive equity can only
establish an explicitly
estimated funding boundary, not verified insolvency. Empty known debt-free scope
retains0.

Current eligible S&P D/SD, Fitch D/RD and Moody's C require a recovery model;
they are not ordinary unrated debt. S&P/Fitch C and Moody's Ca/Caa retain their
existing CCC treatment. `app/stress_risk_inputs.py` preserves applicable primary
evidence as `requires_recovery_model`/`recovery_evidence` without fabricating a
spread bucket. Exact eligible issue evidence takes precedence over issuer
fallback, including performing issues; sovereign fallback must match the
obligation's LC/FC basis. Stale, future, withdrawn, national, short-term or
unenabled manual opinions do not establish this boundary. A separate
`country_requires_recovery_model` flag preserves the relevant systemic FC
opinion. It applies to a known economic country for direct equity/corporate debt
or fund underlying exposures. For direct sovereigns it applies only if the
country-crisis currency differs from base and any holding or signed cash has
exposure to that currency; an irrelevant FC opinion cannot overwrite a
performing LC/base-LC obligation. Fund-manager domicile/default is not underlying
country/credit evidence. Applicable unresolved recovery models produce scoped
ranges, not a guessed100 or fabricated recovery amount.

For example, fund 452,599.35 plus cash 38,819.65 in ILS, if all the fund exposure
is an identified unleveraged ILS money-market fund, produces loss 4,525.9935 on
equity 491,419 (about 0.921% loss; compatibility score 1). This is a conditional
example, not a verified account valuation. All-native cash 100 has loss 0%;
foreign cash 100 versus ILS has loss 15%; unleveraged native money-market exposure
100 has estimated loss 1%, or 15.85% when fully foreign (compatibility scores 1
and 16). These examples assume no larger country stress.
These shocks are declared scenario assumptions, not guarantees or probabilities.

History freezes `provisional_model`, basis, scope/range, point, loss, estimated
net equity, proxy gross, assumptions and scenarios alongside the original strict
result and input evidence. Existing records are immutable. Graphs distinguish
verified, manual-estimate and automatic-estimate observations, break between
method versions, and do not plot range/known-position points as whole-portfolio
observations. Provisional scores are not verified inputs for automatic trade
sizing or risk-reduction ranking. Source-based proxy assumptions retain bounded
reference identity, nominal/payoff facts, maturity and reference retrieval time;
an unused reported coupon can change evidence without changing scenario returns.

### Historical provisional-v1 overlay (immutable observations only)

Saved `portfolio-risk-provisional-v1` observations retain their original meaning:
`provisional_loss = K + U`, where `K` was supported common-scenario loss and `U`
was the absolute value of each unmodeled top-level holding charged once. The
basis was `unmodeled_exposure_allowance`. Unknown/stale/future values or unmodeled
payoffs instead used `missing_valuation_ceiling`, score100 and null loss. This
precautionary ceiling did not establish insolvency. V1 is no longer computed for
current assessments and is not silently reinterpreted as the asset-aware model.

### Completing missing inputs

The expanded Missing risk inputs section retains its existing review actions
and offers retrieval with API then AI (default), API only, or AI only. Public
API adapters require no registration or provider key. Supported adapters resolve
SEC issuer identity/exact dated filing leads and Treasury exact-CUSIP reference
terms; they do not infer economic currency weights from reporting currency or
economic country allocation from an address. Auction yields do not become a
current discount yield or spread. Other fields proceed to bounded AI research
when selected; unsupported or unverifiable evidence remains an explicit gap.

`app/risk_input_retrieval.py` coordinates authenticated owner-bound jobs and
schedules. One request selects at most three securities and shares the existing
eight model/eight REST/eight web call limits across its single AI child.
The public API stage makes at most two requests per selected security. Selection,
remaining coverage, per-field outcomes and source links are visible. Null/all
scope advances bounded batches; an explicit selected scope repeats that scope.
Admin/Operator may run retrieval or save its schedule; Viewer can inspect.
Scheduled execution rechecks its owner's current permissions, uses temporary
scoped credentials and cleans them up. Ordinary scoring remains cache-only.

Research planners receive only allowlisted authenticated REST tools and may
select request-bound source/record IDs. Application publication validates the
actual fetched primary source, exact security/issuer identity, evidence scope,
observation date, publication cutoff and units. A company mention in another
issuer's filing does not establish identity. Economic allocation evidence needs
a dated source; a retrieval timestamp does not supply its observation date.
Literal 100% allocation extraction requires whole affirmative current issuer
statements. Negations, exceptions, intentions, hypotheticals, adjacent
retractions/conflicting statements and historical headings do not become full
current allocations. Explicit statement dates must match the bound report date;
ambiguous prose stays missing. Dated economic allocations are active only within
the declared 550-day evidence horizon.
Static reference terms retain their own contract dates; current yield/spread
expiry remains seven days. Store public evidence separately from manual local
overrides. Editing notes or static terms must not refresh an inherited market
observation date. Derived risk refreshes against the new evidence revision
without discarding saved market quotes or changing the external import source.

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

New observed records carry v4, score/estimate/incomplete status, input/rating
evidence, source revision, assumptions and actual captured FX. Old v2/v3 observations
remain immutable and retain their heuristic explanations. History does not connect
lines across model versions or estimate statuses and never plots a null as zero.
Observed days are not retrospectively backfilled. Scenarios use their coherent
captured as-of date, parameters, prices and FX; later live updates do not rewrite
them. New calculations capture current evidence. Simulation totals retain their
Investment-account scope; risk-reduction alternatives retain canonical dashboard
scope. Source corrections, rating/parameter/country changes and provider evidence
enter the capture/publication guard.

Prospective risk/profit comparison stores a server-derived immutable equity,
ledger, dated mark and FX snapshot alongside each risk observation. Monetary
P&L is `ending equity - baseline equity - recorded net external flows`, never
an inferred return percentage, TWR/MWR or investment-correctness grade. Internal
trades, dividends, interest and fees are already in equity and must not be
double-counted. New unclassified cash reconciliations and unvalued in-kind
transfers break comparisons. Foreign flows require evidenced flow-date FX;
later observations cannot backfill an earlier missing fact. Missing/stale marks,
ledger corrections, unreconciled quantities, account scope/model/currency/epoch
changes and malformed comparison evidence create visible gaps and fresh
baselines. All registered non-ESOP accounts, including zero accounts, define
total scope; unaffected accounts can retain their own baselines. Never use
reconstructed account-trend profit as an observed performance history.

Read-time comparison metadata may be derived, but stored risk/evidence JSON is
immutable. Validate optional imported comparison evidence before dereferencing
it, including economic scope/epoch, total-to-account equity, ledger-derived
cash, action/amount/flow signs and account equity from signed quantities and
positive native marks. Reject zero-quantity nonzero values and sign-contradictory
position values. Every FX fact must match its source and reporting currencies;
future-dated evidence may never enter the historical flow FX pool. A corrupt or
inconsistent snapshot stays a visible risk point with unavailable P&L and breaks
the comparison segment. A user-authorized history restart deletes only
the exact `risk_history_v1:` preference prefix atomically and advances a durable
epoch; stale pre-reset capture tokens must fail across processes and restarts.
Do not delete transactions, prices, account snapshots or unrelated histories,
and never run a repeating startup purge. After a restart the first eligible
observation inside a selected period establishes its actual timestamped baseline.

Planner risk projections use the same signed ledger cash as simulations: BUY
subtracts notional and the fee allowance; SHORT adds proceeds and subtracts the
fee allowance. With equal execution and valuation prices, both preserve net
equity before fees. Reserved collateral remains an asset and constrains only the
planner's separate spending policy. Projected trades mutate only the exact
symbol, normalized market, currency and asset class; other listings remain
separate, while legal-issuer risk aggregation remains shared. Holdings Risk
sorting follows the displayed raw loss percentage when available; a range or a secondary
known-position point is not a sortable whole-exposure score.

Regression evidence includes `tests/test_stress_risk_model.py`,
`tests/test_stress_risk_inputs.py`, independent financial/QA tests, simulator,
history, source-revision and browser/localization checks. Software tests do not
validate financial forecast accuracy.

History integration acceptance must include actual serialized enriched portfolio
shapes. Dated normalized marks ordinarily live at `price_ranges[period].current`
and `current_date`; enrichment does not promise `stress_risk.valuation_date`.
Use the latest eligible saved quote and reconcile quote times signed quantity
to holding value. Actual FX providers use `quote.time` for the observation date;
cache/retrieval timestamps do not replace it. Conversion must match the shared
dashboard's explicit-direct-pair priority, falling back to the inverse only when
no usable direct quote exists. Synthetic convenience fields alone cannot prove
the runtime data contract works. Include zero/tiny loss and just-above-100%
display cases alongside ordinary, concentrated, cash-heavy and leveraged money
examples before release.

## Financial plausibility before publishing scores

Financial QA must reconcile the actual holdings, signed ledger cash, valuation
dates and base-currency FX, then independently derive scenario loss in money and
percent before accepting the displayed score. Explain the result using asset mix,
concentration, currency and funding. Challenge ceiling-like results against known
unleveraged native cash or money-market exposure: missing evidence does not
establish any capital-loss scenario. A compatibility score 100 needs enough
supported loss to round/cap at 100, or the separately labelled known
nonpositive-equity funding boundary. Positive native cash dilutes market
loss; foreign cash retains currency exposure. The combined score must use one
pooled scenario, since different accounts can have different worst scenarios.
Passing software tests or repeating a prior formula is not financial sign-off.
Keep proxy assumptions, incomplete coverage and stale saved marks visible in
the explanation and independently recheck actual account outputs after changes.

Before changing this model again, freeze the financial question, denominator,
units, horizon, scenario set, evidence rules, policy controls, intended score
claim and raw monetary examples before viewing prior preferred rankings. Compare
native cash, foreign cash, money-market funds, diversified/concentrated equities,
duration/credit bonds, borrowing and shorts. Missing-data confidence never becomes
capital loss. Run an independently owned, predeclared experiment set including
at least 50 distinct economic cases when reassessing the formula; retain exact
inputs, independent calculations, execution script, results and differences.
Scenario simulations test arithmetic and plausibility, not forecast calibration.
Audit every display, history, ranking, alert and sizing consumer when units change.
Do not lower shock severity, add a nonlinear score curve, or normalize to a chosen
benchmark merely to get a desired number. Version any justified change and keep
prior observations immutable.

## Declared application controls in v4 units

These are application policies, not empirically calibrated risk or suitability
categories. Compare unrounded raw stress-loss percentages; display rounding must
not relax controls. For an existing v3 policy expressed in doubled-loss points,
divide its loss thresholds/deltas by two and preserve its relative ranking weights.
Removing integer-score rounding can slightly alter a boundary; this is an explicit
switch to the stated unrounded economic units.

* Planner maximum stress loss: 37.5%; maximum increase: 2.5 percentage points
  with existing positions, 12.5 points for the first position. Existing 60/40
  sizing bands become 30%/20%; the greater-reserve threshold becomes 30%.
* Preserve candidate ranking's financial weight relative to concentration/request
  terms: `2*after_loss_pct + 4*max(0, after_loss_pct-before_loss_pct)`, followed by
  the unchanged non-risk terms. These coefficients preserve the old relative
  ordering before integer rounding; they do not calibrate the result.
* Stress-loss watch above 20%, alert above 30%; known nonpositive equity has a
  separate funding alert. Name the threshold and observed percentage instead
  of assigning general High/Extreme risk labels. Keep incomplete/estimated
  evidence visible and never treat a provisional estimate as verified sizing.
* Risk-reduction alternatives compare raw loss-percent changes in one common
  pooled scenario model, with numerical tolerance, without a forced minimum
  integer-point improvement. Gains/losses across accounts pool before the max;
  do not add independent account worst losses.

Conditional anchors: diversified foreign equity 63 plus foreign cash 37 against
ILS loses `63*0.49+37*0.15=36.42` per equity 100 (display 36.4%; score 36).
Equity 94 plus cash 6 loses `94*0.49+6*0.15=46.96` (47.0%; score 47).
Broad native equities 100 lose 40%; broad foreign equities lose 49%; a concentrated
direct issuer retains its separate fixed-FX 60% distress assumption. These
examples require that no larger country/other common scenario governs.

## Primary methodology evidence (reviewed 14/11/2026)

The [BCBS stress testing principles](https://www.bis.org/publications/201810-guidelines-stress-testing-principles)
(17/10/2018) support documented scenarios and independent validation. The
[BIS executive summary](https://www.bis.org/publications/fsi-summary-stress-testing-executive-summary)
explains that stress scenarios do not establish their occurrence probabilities.
Neither source calibrates this application's shocks or scalar.

[SEC margin guidance](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-29)
(10/06/2021) supports the borrowing and greater-than-invested-capital loss
distinction. [SEC fixed-income guidance](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-86)
(26/06/2013) explains rate, coupon and maturity sensitivity, including sovereign
market-price risk. [SEC money-market fund guidance](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/updated-12)
(04/11/2024) supports the distinction between short-term liquid investments and
remaining NAV/liquidity/inflation risk. The 1% MMF proxy remains an analyst
assumption; no cited authority guarantees that ceiling.

## Historical v3 and provisional-v2 scales (immutable observations only)

Saved `portfolio-risk-v3` and `portfolio-risk-provisional-v2` observations use
`round(min(100, 200 * L/E))` with their original scenario/proxy evidence. Score
60 meant 30% modeled loss. Their integer points are not v4 loss percentages and
must not be relabelled or numerically halved after rounding. Old observations,
raw losses, source facts, estimates and validity states remain unchanged. V4
preserves the repricing/scenario assumptions and changes the scalar's declared
meaning; history must break across that model transition.

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
