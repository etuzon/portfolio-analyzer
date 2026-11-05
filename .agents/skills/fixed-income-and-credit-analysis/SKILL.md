---
name: fixed-income-and-credit-analysis
description: Analyze bond cash flows, price and yield conventions, duration, convexity, credit, covenants, refinancing, and inflation linkage. Use for fixed-income valuation and portfolio rate/credit exposure, including Israeli and foreign bonds.
---

# Fixed Income And Credit Analysis

Resolve instrument, currency, par, quote convention, settlement, coupon schedule,
maturity, seniority, issuer, and embedded options. A ticker or current yield does
not establish cash flows or credit quality.

- Read offering documents and issuer evidence. Retain day count, frequency,
  business-day rules, amortization, indexation, options, covenants, and collateral.
- Separate clean price, accrued interest, and dirty settlement amount. Prices may
  be percent-of-par or normalized currency values; normalize exactly once.
- Distinguish coupon, current yield, YTM, yield to call/worst, and realized return.
  State compounding, reinvestment, default, settlement, and option assumptions;
  quoted yield is not a guaranteed holding-period return.
- Separate risk-free curve, spread, liquidity, and FX. Do not apply spread twice
  when it is already part of an all-in yield shock.
- For small parallel yield changes, consistently use modified duration/convexity:
  `delta_price/price ≈ -Dmod*delta_yield + 0.5*C*delta_yield^2`, yields in decimals.
  Reprice for large/nonparallel changes or use appropriate effective/key-rate
  models for embedded options. Label approximations and inputs.
- Inflation-linked bonds require base index, lag, linkage rules, and nominal/real
  distinctions. Floaters need reset/reference-rate terms and retain spread risk.
- Evaluate liquidity, coverage, leverage, maturities, covenant headroom,
  refinancing, seniority, and recovery. Ratings are dated opinions, not default
  probabilities or replacements for issuer analysis.
- Separate default probability, loss given default, exposure, and horizon for
  credit-loss estimates. Do not convert heuristic scores or spreads to calibrated
  default probabilities without a justified model.

Return cash-flow/quote assumptions, valuation/sensitivities, credit evidence,
liquidity/refinancing risks, and missing terms. Use `$financial-data-quality` for
normalization and `$portfolio-stress-and-liquidity` for combined exposures.
