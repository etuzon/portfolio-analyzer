---
name: portfolio-stress-and-liquidity
description: Evaluate portfolio scenarios combining equity, rate, FX, credit, funding, and liquidity shocks. Use for concentration, leverage, cash needs, collateral uncertainty, and stress testing; keep scenario losses separate from calibrated probabilities and broker margin rules.
---

# Portfolio Stress And Liquidity

Define position/cash snapshot, included accounts, instrument conventions, base
currency, liabilities, horizon, and purpose. Distinguish household wealth from
Investment-account-only scope; follow the product's actual contract.

- Reconcile signed positions, cash, accruals where relevant, FX, shorts, borrowing,
  and gross/net exposure first. Negative cash is borrowing; short proceeds do not
  create equity or establish verified available cash.
- Keep holdings immutable. Simulations do not submit orders, save actual trades,
  repair ledgers, or write to external import sources.
- State units and conditioning assumptions for equity, rate/spread, FX, volatility,
  funding, and liquidity shocks; describe simultaneous versus sequential effects.
- Reprice instruments before currency conversion. If FX is investor-currency
  units per local unit, combined return is
  `(1+local_return)*(1+fx_return)-1`, not the sum of percentages. Resolve inverse
  FX quotes explicitly.
- Define baseline conversion and stressed FX paths separately for each foreign
  currency. A supplied baseline rate does not define a stress rate; an unchanged
  FX path must be an explicit scenario assumption. Name both gaps when neither
  is supplied, and preserve affected unavailable results until resolved.
- Use signed quantities for long/short P&L. Avoid duplicate shocks already included
  in instrument returns, fund holdings, or all-in yields. Use fixed-income methods
  for bonds and suitable nonlinear repricing for options.
- Model obligations, settlement, liquidity, maturities, and transfer restrictions
  separately from market loss. Do not assume cash is fungible across accounts.
  Broker collateral/margin availability remains unknown without verified terms
  or an explicitly hypothetical model.
- Preserve unknown prices, FX, cash, classifications, and exposures. Show known
  results/coverage but label affected totals unavailable or partial; omission is
  not zero risk.
- Distinguish illustrative stress, historical replay, VaR/expected shortfall, and
  calibrated joint probabilities. Do not attach unsupported probabilities;
  correlations can change under stress.
- In portfolio-analyzer use the shared maintained portfolio-risk model for the
  displayed score. Scenario loss is separate from risk-score weights, loss
  probability, and broker permission.

Return baseline reconciliation, scenarios, position/account P&L, post-shock equity,
concentration, liquidity/funding needs, missing coverage, and approximation limits.
Verify raw examples with shorts, missing inputs, inverse FX conventions, and
offsetting balances where relevant.
