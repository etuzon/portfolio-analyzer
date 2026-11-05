---
name: quantitative-research-and-model-validation
description: Design and audit investment backtests, event studies, factor analysis, and forecast validation with chronological data and explicit uncertainty. Use for financial performance or predictive claims, not as a substitute for software regression tests.
---

# Quantitative Research And Model Validation

Declare the question, target, horizon, information set, universe, benchmark,
metric, and inclusion/exclusion rules before measuring success.

- Separate implementation checks from evidence of prediction or investment
  performance. Passing software tests proves neither.
- Use publication cutoffs, macro vintages, dated constituents, delisted securities
  where relevant, and consistent corporate actions. Disclose coverage gaps instead
  of claiming a bias-free backtest.
- Separate calibration, chronological holdout/walk-forward, and prospective
  forecasts. Freeze models/predictions before outcomes. Do not select horizons,
  labels, thresholds, or exclusions after seeing successes.
- Avoid overlapping train/test information. Count independent economic units,
  not repeated saves or correlated views of the same company/event. Use time/group
  aware uncertainty methods as relevant and disclose dependence limitations.
- Specify simple/log, price/total, native/investor-currency, benchmark, cash-flow,
  and timing conventions. Include fees, spreads, turnover, financing, and instrument
  availability assumptions for executable-strategy claims.
- Separate correlation, factor exposure, predictive association, and causality.
  Event studies need event/estimation windows, expected-return model, and confounder
  assessment. Post-news movement alone is not causal proof.
- For classification show class frequencies, confusion counts, coverage, baseline,
  and uncertainty. Evaluate probability calibration and proper scores where used;
  evidence confidence differs from outcome probability.
- For continuous forecasts report suitable errors and benchmark comparisons. Do
  not compute percentage errors blindly around zero.
- Record material variants, missing/ungraded results, and selection rules.
  Inconclusive stays ungraded instead of becoming a success/failure or silently
  excluded observation.
- Version changes and evaluate on untouched evidence. Do not promise an accuracy
  target or tune until an arbitrary pass percentage appears.

Return protocol, lineage, frozen configuration, subgroup/horizon results,
uncertainty, exclusions, and precise claim boundaries. For portfolio-analyzer use
its versioned outcome contract and validation gate; do not claim stock-return
prediction from a model tested only on future accounting comparisons.
