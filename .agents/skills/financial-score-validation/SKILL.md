---
name: financial-score-validation
description: Validate the economic meaning, scale, evidence and presentation of financial scores before reporting or changing them. Use for portfolio risk, investment scores and financial model reviews; not cosmetic finance-themed edits.
---

# Financial Score Validation

Make a score economically interpretable before accepting its arithmetic. Finance
owns the method; independent QA derives expectations from raw inputs. Follow the
repository's role and authorization rules.

## Meaning before numbers

- Define the question, included assets/accounts, reporting currency, observation
  cutoff, horizon and score direction. Distinguish a loss amount, loss percentage,
  relative rank, declared heuristic, probability and predictive estimate.
- Write the formula, units, denominator, anchors, rounding and clipping. Explain
  what zero, a middle value and the upper endpoint mean financially. Identify
  assumptions and custom thresholds as choices. External methodology does not
  validate the application's weights or labels.
- Freeze the proposed method and acceptance examples before comparing prior
  rankings or current account outputs. Do not fit a multiplier to reassuring
  numbers. Compare retained prior methods afterward.
- A quantity such as scenario capital-loss percent needs transparent units and
  sensitivity checks. Empirical calibration needs dated observations, reference
  portfolios, a defined horizon and independent validation. Synthetic simulations
  establish neither loss probabilities nor investment performance.

## Financial plausibility

- Reconcile holdings, signed cash/debt, prices, FX and net equity. Check instrument
  identity, quote units, source observation dates and evidence eligibility before
  joining country, issuer, fund or security credit information.
- Independently derive the loss in money and percent. Explain major outputs
  through asset mix, currency, concentration, credit, rates and funding. Passing
  software tests does not establish this explanation or validate the score scale.
- Challenge controlled reference portfolios: native/foreign cash, an unleveraged
  money-market fund, different bond durations/credit, diversified/single stocks,
  borrowing and shorts. Check rankings, one-factor sensitivities, ordinary
  portfolios near the ceiling, and severe portfolios hidden by clipping.
- Positive native cash dilutes modeled market loss in an otherwise unchanged
  unleveraged portfolio. Foreign cash retains FX exposure. Money-market funds
  need appropriate declared stresses, rather than an equity shock or a manager's
  default risk. A low result does not establish that an instrument is risk-free.
- Apply security and country credit to the obligation they describe, including
  sovereign local/foreign-currency distinctions. Fund-manager credit is not the
  underlying portfolio's credit. Check duration and payoff conventions.
- Pool positions in the same scenario before selecting the worst loss. Do not
  add separate account worst cases or average clipped/rounded scores. Reprice
  locally before compounding FX; reconcile short proceeds and liabilities.
- Missing evidence changes confidence, eligibility or scope; it does not establish
  a financial loss. Unknown values are not zero. Keep unsupported payoffs and
  partial scopes explicit. A capped index range is not a bound on unknown
  leveraged loss. Nonpositive equity has an undefined percentage denominator,
  rather than a fabricated percentage. Preserve losses above display ceilings.

## Simulations and independent review

Match the experiment to the claim and the user's requested count. Use distinct
economic cases and controlled sensitivities, not repeated inputs or random
outputs without an oracle. Freeze raw fixtures and independent expectations
before examining implementation results. Retain each case's purpose, inputs,
net equity, scenario loss, percentage, score, scope and verdict, together with
the exact runner and cutoff. Keep private financial fixtures in ignored local
artifacts; use synthetic fixtures in version control.

Check numerical consistency and economic plausibility separately. Include
boundaries, missing/stale data, offsetting exposures, currency changes and account
pooling. Count statistical observations separately from simulations and software
tests. Obtain fresh independent review for final numerical behavior and claims.

## Presentation and shared consumers

- Show the unit and assumptions where the user reads the number. Expose underlying
  financial loss, FX effect, dates, missing coverage and supported scope. Do not
  imply a validated risk class through an unexplained adjective. Declared
  heuristics can be useful without being described as calibrated.
  When units or labels change, verify compact table headers, sort controls and
  numeric cells at desktop/mobile breakpoints in each active language. Preserve
  clipping assertions; expand the appropriate column instead of hiding its label.
- Audit dashboard, holdings, accounts, sorting, history, simulations, sizing and
  alerts. Convert policy thresholds and ranking weights explicitly when units
  change; a new display scale must not silently relax another financial control.
  Use unrounded economic quantities for policies, rather than capped or rounded
  compatibility scores; distinguish zero displayed precision from zero loss.
- Version numerical behavior and meaning. Keep frozen legacy values in their
  original units, separate chart scales, and never claim improvement from a
  formula change alone. Update affected Help in each supported language.
- Report the economic explanation, executed checks and claim limits. Keep failed
  financial-method or acceptance checks open; software success must not hide
  them. Skills improve review, rather than guaranteeing correctness or authorizing
  data writes, trades, publication or deployment.

Read the implemented [portfolio risk contract](../trade-simulation/references/portfolio-risk.md)
for risk models or [company outlook contract](../company-outlook-model/SKILL.md)
for company scores. Use [quantitative model validation](../quantitative-research-and-model-validation/SKILL.md)
when conclusions depend on historical or predictive performance.
