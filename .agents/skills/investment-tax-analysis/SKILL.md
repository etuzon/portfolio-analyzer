---
name: investment-tax-analysis
description: Analyze investment cost basis, realized gains and losses, withholding, foreign tax credits, and after-tax comparisons for the relevant jurisdictions, tax year, and account type. Use for tax research or method review, not filing or trade execution.
---

# Investment Tax Analysis

Produce a traceable, conditional tax analysis. This skill supplies a method; it
does not establish a tax rate, eligibility, or an implemented application feature.
For a larger team task, return the tax contract to the existing coordinator;
do not start another coordination workflow.

## Resolve Scope and Authority

- Establish relevant residence and taxing jurisdictions, tax year, analysis
  cutoff, taxpayer/entity status, and taxable, exempt, or deferred account type.
  Collect citizenship, treaty eligibility, instrument/fund domicile, or personal
  facts only when they can change the treatment. Do not infer these from language,
  broker location, trading currency, or an account's display name.
- Identify the instruments, transaction types, ownership, recognition dates,
  reporting currency, and question: historical reconciliation, estimated annual
  liability, incremental sale tax, or comparison of future scenarios.
- Verify each applied rule against current official tax-authority guidance,
  legislation, or official treaty text for the applicable jurisdiction and year.
  Record the direct URL, relevant provision, effective period, version/publication
  date, retrieval date, and applicability. A current page need not describe a past
  tax year. Separate enacted rules, proposals, and historical knowledge cutoffs.
- Broker statements establish observed transactions or reported treatment; they
  do not independently establish the governing law. Explain source conflicts.
  Keep unsupported rates, exemptions, thresholds, filing obligations, and treaty
  benefits unknown. Resolve material ambiguity with qualified local tax advice
  rather than choosing the most favorable interpretation.
- Missing material context permits bounded scenarios with named assumptions,
  not a definitive personalized liability. Ask only for facts needed to resolve
  the requested conclusion; continue work that does not depend on them.

## Reconstruct Basis and Recognized Amounts

- Retain transaction/lot identity, source records, dates, quantities, gross
  consideration, fees, withholding, currencies, FX observations, and adjustments.
  Reconcile opening lots, purchases, disposals, transfers, actions, and closing
  holdings. An account transfer or current market value is not a substitute for
  acquisition history. Missing basis must not silently become zero.
- Verify permitted lot identification, matching, holding-period, and recognition
  conventions before allocating basis. Preserve provenance through splits,
  mergers, spin-offs, reinvestments, returns of capital, gifts, and transfers when
  present; establish applicable treatment instead of assuming a generic action.
- Define amounts as gross or net. Use gross proceeds/income before withholding;
  show costs and withheld tax separately. Reconstruct gross amounts from net cash
  only when supporting components are known. Do not deduct withholding as both
  an expense/basis adjustment and a tax payment without verified legal grounds.
- Use the verified tax-currency conversion convention for acquisitions,
  disposals, income, costs, and tax payments. Retain each rate, date, direction,
  and rounding rule. Do not convert a native-currency net gain at one date when
  the applicable rules require separately converted components. Verify any
  indexation or separate FX treatment; avoid double counting currency gains.
- Start the reconciliation with gross disposal proceeds minus allowable disposal
  costs minus allocated adjusted basis. Distinguish this arithmetic result from
  taxable recognized gain/loss, unrealized gain/loss, and income distributions.
  Apply classification, exclusions, deferrals, and loss restrictions only after
  verifying their rules. Market loss alone does not establish a deductible loss.
- Reconcile annual netting, offsets, carryovers, and expiry by verified income
  category and year. A loss's face amount is not its tax saving; quantify benefit
  only when eligible use, timing, and applicable marginal tax effects are supported.
  Use [financial-data-quality](../financial-data-quality/SKILL.md) for material
  source, identity, corporate-action, or currency-normalization problems.

## Separate Tax Liability, Withholding, and Credits

- Present source tax withheld, gross liability by jurisdiction, eligible credits,
  prepayments applied, refunds/reclaims, and remaining payable as separate stages.
  State whether every liability figure is before or after credits. Observed
  withholding is neither proof of final liability nor proof of credit eligibility.
- Verify income sourcing, treaty conditions, creditable tax, caps, ordering,
  currency conversion, carry periods, and claim timing before calculating foreign
  tax credits. Leave unsupported eligibility, caps, and timing unknown. A credit
  reduces eligible tax; a deduction changes its base. Neither is automatically a
  cash refund. Do not count the same tax as both reclaimed and credited.
- Reconcile dated cash across jurisdictions: gross cash minus costs minus taxes
  actually paid plus refunds. Include residual payments and avoid subtracting
  both full final tax and withholding already applied toward that tax. State
  which cash has occurred, which is forecast, and which remains contingent.
- Synthetic arithmetic only: gross proceeds 1,000, fee 10, and adjusted basis 800
  give a pre-rule result of 190; withholding 25 leaves settlement cash 965. If
  total final tax is separately assumed to be 30 and all 25 is applicable against
  it, another 5 is payable and ultimate cash is 960. These assumptions establish
  no jurisdiction's recognition, rate, or credit entitlement.

## Compare After-Tax Outcomes

- Compare consistent initial wealth, horizons, cash needs, currencies, and
  economic exposures; disclose differences in risk, fees, liquidity, and financing.
  Compute incremental tax from complete scenario liabilities when interactions
  matter, rather than multiplying an isolated gain by an unverified flat rate.
- Show dated taxes, distributions, reinvestment, transaction costs, and terminal
  values. Expose remaining deferred tax at the horizon. Distinguish permanent tax
  saving from deferral and from an assumed future refund or loss utilization.
  Use stated discount/return assumptions for time-value comparisons; label
  sensitivity cases and define denominators for any after-tax return or tax rate.
- Return scope, official rules and dates, raw-input lineage, formulas, gross/net
  and payment reconciliation, known results, conditional scenarios, and material
  unknowns with the next evidence needed. Keep synthetic examples separate from
  jurisdiction-verified results; retain inputs and executable calculations for
  analyses actually run. Do not treat missing tax inputs as zero.
- Research and scenario analysis authorize no trades, tax filings, elections,
  broker/source writes, production-data changes, or deployment. Follow the
  specific task's authorization for any separately requested action.
