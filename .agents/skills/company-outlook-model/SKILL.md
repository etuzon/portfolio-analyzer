---
name: company-outlook-model
description: Review or change the implemented portfolio-analyzer financial comparison score, annual report inputs, frozen forecast evaluation, or validation gate. Use for formula rechecks and financial-model fixes in this repository.
---

# Implemented company outlook model

This documents `report-outlook-v5`. Read the actual code before changing a rule;
keep this reference aligned with it. A financial rule that changes output needs
a new model version. Software regression tests do not establish forecast accuracy.

## Source of truth

- `app/outlook_scoring.py`: model version, weights and saved outcome contract.
- `app/main.py`: `_annual_report_rows`, `_outlook_company`, `_fundamental_score`,
  `_company_outlook_payload`, `_evaluate_prediction`.
- `app/providers.py`: `_sec_annual_facts`, `_fundamentals_from_facts`, parser cache marker.
- `app/local_portfolio.py`: immutable prediction history and `_outlook_validation_gate`.

## Financial data

SEC flow facts require a verified inclusive duration of 335–395 days; annual
filing labels alone do not establish annual duration. Instantaneous balance
sheet facts must match the exact fiscal end. Joined flow periods must also match
their starts exactly. Select only revisions filed by the as-of date.
Normalized SEC snapshots require `sec-periods-v2`; older derived snapshots are
rebuilt from retained raw facts instead of being trusted.

Long-term debt uses an explicit current-plus-noncurrent total, or matched
current and noncurrent components with the same fiscal date and filing.
Do not add the total to its components or substitute one component for total
debt. Net debt and total debt are not aliases for long-term debt.

Generic annual rows are deduplicated by fiscal end before growth calculations;
the latest eligible filing wins. Historical requests require a filing date;
fiscal end is not proof of public availability. Future fiscal/filing dates and
nonfinite or boolean financial values are excluded.

Annual growth requires consecutive fiscal ends 335–395 days apart and consistent
reported currency when supplied. Growth is `(current-prior)/abs(prior)*100`,
with a strictly positive prior denominator. A loss-to-profit turnaround and
multi-year gap are not ordinary annual growth rates; keep the raw amounts but
leave that comparison unavailable. No silent annualization.

Margins require positive revenue. Free cash flow is operating cash flow minus
absolute capital expenditure. Cash conversion is FCF/net income and requires
positive net income; it is descriptive, not a second cash-quality score.
Current ratio requires nonnegative assets and positive liabilities.

## Score: comparable company finances, 0–100

All companies use **net margin**, with no operating-margin substitution.
Each metric is compared with the same peer median:

| Measurement | Raw weight | Spread | Favorable direction |
|---|---:|---:|---|
| Revenue growth | 12 | 20 percentage points | Higher |
| Net-income growth | 10 | 30 percentage points | Higher |
| Net margin | 10 | 20 percentage points | Higher |
| FCF margin | 5 | 15 percentage points | Higher |
| Long-term debt/revenue | 2 | 30 percentage points | Lower |
| Current ratio | 1 | 0.8 | Higher |
| Annual net-margin change | 5 | 5 percentage points | Higher |

```text
points = round(clamp(weight/2 + (value-median)/spread * weight/2, 0, weight), 1)
# Reverse value and median for debt/revenue.
final = round(sum(points) / 45 * 100, 1)
```

The denominator is always 45. Missing weights are never redistributed.
Use a common metric mask across the target and every usable peer. A final score
requires all 45 weight units and at least two usable comparable peers; otherwise
return `score=null`, `score_status=insufficient`, `direction=inconclusive`.
Do not save a directional prediction for an incomplete analysis. Continue to
show available reports, missing measurements and coverage. Where meaningful,
`score_range` bounds the points under unknown measurements, not likely returns.

A usable peer belongs to the comparable industry cohort, has revenue growth and
net margin, and has a fiscal end within 120 days of the target's. Never fall back
to unrelated industries. Reports older than 550 days, or future reports, cannot
support a current score. Banks, insurers, REITs and other financial businesses
need a specialized model; a manual cohort name must not override actual industry
or sector. Show `industry_model_required` and the available reports.

Ranking is informational and uses the same shared metrics, requiring at least
32/45 available weight units. Competition rank is `1 + strictly higher scores`;
display ties explicitly. A rank does not award bonus points.

Industry medians and related-company reports remain context. Peer counts,
history, coverage, related names and relationship labels add **zero** score
points. Industry context uses revenue/profit/margin weights 8/6/5, displayed
separately on a 0–100 scale only with adequate evidence. These relationships
must not be described as measured causal exposure.

Equal complete peer evidence gives 50/100. Scores below 35 are Weak/negative;
35 to below 65 Mixed/neutral; 65 to below 80 Good/positive; 80–100 Strong/positive.
These weights and thresholds are declared deterministic choices, not calibrated
probabilities or demonstrated investment performance.

## Saved forecast outcome

Freeze `peer-revenue-margin-v1` with the baseline, exact peer set, model version,
score and thesis. Its question is whether the **next comparable annual report's
revenue growth and net margin** are both above, below, or mixed versus those
peers. This is a narrower outcome than every driver of the financial score.

- Select the next annual period, 335–395 days after each saved baseline, with
  verified filing date by the horizon and current known date. Do not choose a
  more favorable later year. Peer fiscal ends remain within 120 days of target.
- All saved peers must supply comparable results; a smaller surviving cohort
  cannot replace the frozen group. Missing data/provider errors yield ungraded,
  retryable `inconclusive`, never an absolute-performance fallback.
- Both differences above +1 revenue percentage point and +0.5 margin percentage
  point mean positive. Both below -1 and -0.5 mean negative; other cases, including
  exact tolerance boundaries/equality, mean neutral.
- Grade 100 for an exact predicted/actual direction match; otherwise 0. Missing
  evidence receives no grade. The tolerances are predeclared model choices.
- Checking a company updates its pending/retryable forecasts using each frozen
  baseline/horizon; completed history and other companies stay unchanged.

Older models retain their saved values and legacy evaluation algorithms. Do
not silently recompute their predictions as v5 or count them as v5 validation.

## Prospective validation

`recorded_at` is server-set and immutable; legacy rows have no verified recording
time. Current-model validation requires scored, frozen prospective predictions
whose baseline filing dates were known on their recorded date. Historical and
batch calibration/holdout labels alone are not independent evidence.

Actual filing must be strictly after the recorded date and already observed
by evaluation. Require the saved outcome contract and consistent binary grades.
Count each company/actual annual period/outcome contract once, across batches,
baselines and horizons. Earliest frozen observations govern; do not choose a
successful later retry. Legacy grades remain visible separately.

The gate needs at least 30 eligible current-model economic observations, a
direction match rate at least 75%, and a 95% Wilson lower bound at least 75%:

```text
lower = (p + z²/(2n) - z*sqrt(p*(1-p)/n + z²/(4n²))) / (1 + z²/n)
z = 1.959963984540054
```

Expose eligible/excluded counts, current model, point estimate, lower bound and
failed reasons. This is forward observational validation under a binomial
assumption; market/industry dependence and selection still limit interpretation.
Do not claim stock-return prediction, full-thesis validation or guaranteed gains.

## Recheck and release

Use temporary `DATA_DIR` and `CONFIG_PATH=config.example.yaml` before imports.
Relevant regressions include `test_outlook_scoring_v5.py`,
`test_sec_financial_periods.py`, `test_outlook_validation.py`,
`test_company_report_check_history.py` and the v5 frontend tests. Test raw report
periods/revisions/debt, missing-data masks, equal/endpoint scores, context-only
changes, frozen-cohort outages/retry, legacy preservation, and genuine prospective
validation alongside repeated/calibration/mixed-model exclusions.

Use independent QA before release. Explicit user commit/deploy requests use the
repository's scoped `scripts/commit-and-deploy.sh` workflow.

Primary methodological references: [SEC fact periods and filing data](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[CFA financial analysis](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/financial-analysis-techniques),
and [CFA chronological backtesting and bias](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation).
These sources do not endorse the app's declared weights or thresholds.
