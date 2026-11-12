# Shared portfolio risk: portfolio-risk-v2

Implemented by `riskScoreForItems` and `portfolioRiskSnapshot` in `web/app.js`.
The dashboard account, portfolio, industry and holding badges and the simulator
use the shared scoring rule. This is a declared heuristic, not calibrated loss
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

## Observed risk history

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

## Interactive risk-reduction alternatives

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
