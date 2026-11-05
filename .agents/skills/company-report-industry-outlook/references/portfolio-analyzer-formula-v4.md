# Archived v4 formula and audit

This describes the pre-fix model. Use the active formula guide for new work.

# Portfolio Analyzer: Implemented Formula and Review Guide

## Scope and source of truth

This reference describes the **implemented `report-outlook-v4` formula**, reviewed
on 31/10/2026 in `/etuzon/projects/ai/portfolio-analyzer`. It documents current
behavior, including known defects. Proposed improvements below are **not yet
implemented or validated**. The general recommended weights in
`scoring-and-diagram.md` are design guidance, not a description of this version.

Before a recheck, confirm `OUTLOOK_MODEL_VERSION` and read these functions:

| Responsibility | Code |
|---|---|
| Report dates, growth, ratios | `app/main.py::_annual_report_rows` |
| Company measurements and margin choice | `app/main.py::_outlook_company` |
| Relative comparison and fundamentals | `app/main.py::_relative_points`, `_fundamental_score` |
| Peers, component weights, final score | `app/main.py::_company_outlook_payload` |
| Later-report outcome and grade | `app/main.py::_evaluate_prediction` |
| Aggregate grade and validation flag | `app/local_portfolio.py::company_report_scorecard` |
| SEC fact selection and debt inputs | `app/providers.py::_sec_annual_facts`, `SecCompanyFactsProvider._fundamentals_from_facts` |

Code takes precedence if this reference and implementation diverge. Correct
the documentation and report the mismatch; do not silently change a financial
rule to match an old document.

## What the score means

The score is a deterministic financial screen combining company measurements,
peer conditions and related-company assumptions. It is not a probability of
profit, a stock-return forecast, or demonstrated predictive accuracy.

Current implemented components:

| Component | Actual maximum | Meaning |
|---|---:|---|
| Company fundamentals | 45 | Growth, profitability, cash quality and balance sheet relative to peers |
| Industry conditions | **21** | Peer medians and peer count; the UI allocation says 25 |
| Related-company effect | 15 | Growth and relationship labels of up to four related companies |
| Relative rank | 8 | Rank of the company fundamentals score within the selected group |
| Report-history bonus | 4 | Report and peer counts |
| Data-coverage bonus | 3 | High/Medium/Low count-based category |
| **Implemented maximum** | **96** | Despite a displayed scale of 0–100 |

```text
final = round(clamp(company + industry + related + rank
                    + report_history + data_coverage, 0, 100), 1)
```

The stated component allocation and implemented maximum disagree. A bounded
0–100 screen need not reach 100 to be useful; this discrepancy alone does not
prove poor predictive performance. Resolve the intended allocation explicitly
rather than silently normalizing the result to 100.

## Shared relative-points calculation

For an available value `v`, comparison median `m`, point limit `w`, and spread `s`:

```text
relative(v, m, w, s) = round(clamp(w/2 + (v-m)/max(s, 0.1) * w/2, 0, w), 1)
```

A value equal to the median receives half the available points. Missing values
or medians produce zero from this helper. Percentage values are percentage
points: use `10` for 10%, not `0.10`.

## Financial inputs used by the formula

For growth, the current implementation uses
`(current - previous) / abs(previous) * 100`; a missing value or zero previous
value gives an unavailable growth measurement. It uses the prior available
annual row without adjusting for a multi-year gap. Loss-to-profit and
profit-to-loss comparisons therefore need explicit review.

| Measurement | Current definition |
|---|---|
| Gross margin | `gross_profit / revenue * 100` |
| Operating margin | `operating_income / revenue * 100` |
| Net margin | `net_income / revenue * 100` |
| Net-margin change | Latest net margin minus the immediately preceding annual row's net margin, in percentage points; unavailable if either row lacks it |
| Free cash flow (FCF) | `operating_cash_flow - abs(capital_expenditures)` |
| FCF margin | `FCF / revenue * 100` |
| Cash conversion | `FCF / net_income * 100` |
| Current ratio | `current_assets / current_liabilities` |
| Debt/revenue | Parsed `long_term_debt / revenue * 100` |

Missing numerators or missing/zero denominators give unavailable ratios. The
current implementation allows negative nonzero denominators; this is a known
issue, not an assertion that such ratios are economically meaningful. Parsed
debt is selected from provider fields and is not guaranteed to be total debt.

## Company fundamentals: 45 points

| Measurement | Weight | Spread | Current calculation |
|---|---:|---:|---|
| Revenue growth | 12 | 20 | Relative to peer revenue-growth median |
| Net-income growth | 10 | 30 | Relative to peer net-income-growth median |
| Profit margin | 10 | 20 | Relative to peer profit-margin median |
| Cash quality | 5 | 15 / 40 | Average available FCF-margin and cash-conversion point scores |
| Debt/revenue | 2 | 30 | Reverse comparison, so lower debt/revenue scores better |
| Current ratio | 1 | 0.8 | Relative to peer current-ratio median |
| Net-margin change | 5 | — | 5 points for change >= 0; 1 point otherwise |

FCF-margin uses weight 5/spread 15; cash conversion uses weight 5/spread 40.
If both exist, average their points; if one exists, use it. The cash component
still has a maximum weight of 5.

**Important current missing-data behavior:** unavailable measurements are
removed from `available_weight`, then the available score is rescaled:

A relative-comparison weight is included only when both the company value and
its corresponding peer median are available. Net-margin change needs no peer
median and is included when that change itself is available.

```text
company = round(earned_points / available_weight * 45, 1)
# If available_weight is zero, company = 0.
```

This can inflate sparse evidence. Example: unchanged net margin alone earns
5/5 and becomes **45/45**, although growth, cash flow and debt are unknown.
A fully observed company at every peer median with unchanged net margin earns
25/45. This is a defect to review, not an intended missing-data penalty.

Profit margin currently chooses operating margin when present, otherwise net
margin. This allows different definitions into one median. Calculated cash
conversion is `FCF / net_income * 100`; two negative values can misleadingly
produce a positive ratio. Annual growth uses the prior available row, even if
reporting periods are not consecutive.

## Peers, industry, and rank

Use up to six peer reports. Prefer peers identified as comparable; if none
qualify, the implementation falls back to all supplied peer reports. Provider
industry cohorts and manually asserted industry cohorts are accepted as
comparable. Missing individual values are excluded from medians.

```text
industry = relative(peer_revenue_growth_median, 0, 8, 20)
         + relative(peer_net_income_growth_median, 0, 6, 25)
         + relative(peer_profit_margin_median, 0, 5, 20)
         + (2 if peer_count >= 3 else 0)
```

Industry maximum is 8+6+5+2 = **21**. Industry state is Pressure below 9,
Stable from 9 to below 15, Supportive from 15 upward; without any of the three
peer medians it is Not available.

Sort the target plus ranked peers by fundamentals score descending. Position 1
is strongest in this group, position N weakest; this is not a market-wide rank.
The payload's `ranked_company_count` describes this cohort, which can be smaller
than the displayed company table.

```text
rank_points = 0                            if N <= 1
rank_points = round((N-position)/(N-1)*8, 1) otherwise
```

The target's rank is effectively `1 + number of companies strictly above it`.
This is valid competition ranking: tied leaders can all rank 1. The actual
design/communication concern is that ties are not identified and a completely
tied group earns the full 8-point rank bonus without differentiated strength.
Changing to a midrank or tie-aware percentile would be a model choice, not an
arithmetic correction. A one-company group already gets zero rank points.

## Related-company effect: 15 points

Each of up to four related companies with available revenue growth contributes:

| Relationship value, case-insensitive | Growth > 0 | Other available growth |
|---|---:|---:|
| `demand support`, `customer demand`, `complement` | 5 | 1 |
| `cost pressure`, `supplier pressure`, `substitute` | 1 | 4 |
| Any other relationship | 2.5 | 2.5 |

Sum contributions and cap at 15. Missing growth contributes zero; no related
reports gives zero. Current points depend on company count and free-text
relationship names, without measured exposure. Three growing customer names
can earn the full 15 even when each grows only 1%. Proposed changes must
distinguish unknown evidence from a measured adverse effect.

## Data coverage and report history

The stored machine field is still `confidence`; the forecast UI calls it
**Analysis data coverage / היקף הנתונים לניתוח**. It describes count-based
supporting evidence, not a guarantee or probability of a favorable result.

| Stored value | UI value | Current condition | Bonus |
|---|---|---|---:|
| High | Broad / רחב | Target has >=3 annual rows and >=4 peers | 3 |
| Medium | Moderate / בינוני | Target has >=2 annual rows and >=2 peers, without meeting High | 2 |
| Low | Limited / מצומצם | Otherwise | 0 |

Separately, the history bonus is 4 for >=3 target rows and >=3 peers; otherwise
2 for >=2 target rows and at least one peer; otherwise zero.

These rules currently do not require complete statements, fresh reports, or
usable peer metrics. Do not present them as a comprehensive data-quality test.
In a reproduced fixture, adding four empty peer reports raised the same target
from 60/neutral/Low to 77/positive/High: industry-count +2, rank +8, history +4,
and coverage +3. No usable peer financial evidence was added.

## Labels and later-report evaluation

Current score bands, including fractional scores:

| Score | Label | Stored prediction direction |
|---|---|---|
| >=80 | Strong | positive |
| >=65 and <80 | Good | positive |
| >=50 and <65 | Mixed | neutral |
| <50 | Weak | negative |

There is no separate implemented 0–34 “insufficient” band in v4.

Actual evaluation uses a newer **annual** report after the saved baseline and
within the saved horizon. Reports are normalized newest-first; the evaluator
takes the first eligible one, so this is the latest eligible annual report,
not necessarily the immediately following annual period. The horizon cutoff
uses filing date when present, otherwise fiscal date. With at least two usable
later peer reports, compare
target revenue growth and net margin to the later peer medians: both at/above
means positive, both below negative, mixed signs neutral. Without enough peers,
positive requires revenue growth >0 and margin change >=0; negative requires
both below zero; other comparable results are neutral. Missing comparable
measurements give inconclusive.

Pending with a “no newer report” result requires a nonempty report list and at
least one provider status exactly equal to `ok`. Empty reports, unavailable
providers and stale-only evidence cannot establish absence of a newer report:
they cause a failed check (HTTP 503), preserving the previous completed result.
A missing saved baseline fiscal date fails with HTTP 422. An available newer
saved report can still be evaluated during a provider outage; its existence is
evidence, whereas stale data cannot prove that no newer report exists.

Current grade: 100 when predicted and actual directions match, otherwise 50
when actual direction is neutral, otherwise 0. Inconclusive has no grade.
The scorecard averages these grades. It is not a calibrated probability or a
complete test of every cash-flow, debt, industry and related-company driver in
the original forecast.

The evaluation target changes when usable peer coverage drops below two:
relative performance becomes absolute growth/margin change. In an isolated
case, the same target report graded 100 with two usable peers and 0 after one
peer became unavailable. Define the target in advance; missing peer evidence
must not silently substitute a different forecast question.

The current validation flag requires >=30 evaluated records and average grade
>=75. It does not enforce one model version, independent observations, or an
untouched holdout. Repeated calibration records must not be represented as
independent proof of forecasting quality.

## Improvement and recheck sequence

1. **Input integrity:** reject nonfinite numbers; distinguish annual-duration
   and instantaneous SEC facts; match exact fiscal dates and periods rather
   than calendar year alone; select total debt or properly matched components;
   deduplicate revisions of one fiscal period; establish historical filing
   availability; handle reporting gaps and non-positive profit denominators.
2. **Comparable evidence:** use consistent margin definitions and periods,
   appropriate industry ratios, and a sufficient common measurement set. Avoid
   manufacturing a strong result from unavailable data.
3. **Score mechanics:** specify tie treatment and resolve the 96/100 discrepancy; remove
   arbitrary count-based related-company effects or support them with measured
   exposure. Define missing-data behavior explicitly.
4. **Validation:** specify the forecast target, grading rule and benchmark before
   calibration. Separate model versions and economically distinct observations;
   use chronological evaluation and an untouched holdout. Report actual sample
   counts, failures, exclusions and uncertainty.
5. **Version and documentation:** preserve old prediction scores, baselines,
   thesis and diagrams. Record a new model version for output-changing rules,
   update this reference and regression evidence, and report before/after
   results without claiming unmeasured accuracy improvements.

The initial 31/10/2026 audit rated methodology **45/100**. The fresh recheck
revised the assessment to **40/100** after reproducing additional input,
empty-peer and evaluation failures. Both are subjective design assessments,
not empirical accuracy. The recheck rubric was input integrity 8/20,
comparability 6/20, score mechanics/explainability 12/20, forecast/evaluation
contract 6/20, and validation/governance 8/20. Re-rate only against inspected
code and evidence; passing software tests does not measure forecasting accuracy.

## Recheck evidence: 31/10/2026

A fresh independent review executed 20 isolated cases against v4; a separate
coordinator reproduction confirmed the main score, input and validation
counterexamples. These are synthetic stress fixtures, not measurements of
live-company forecast accuracy. Use the following as regression oracles after
an authorized correction, rather than preserving the defective outputs.

| Case | Observed v4 result | Required review |
|---|---|---|
| Only unchanged margin available | 45/45 versus 25/45 for complete median evidence | Enforce sufficient comparable measurements; expose coverage separately |
| Four peers without any reports | Target 60 to 77; coverage Low to High | Require usable evidence before awarding peer/count/rank support |
| All net margins 5%; only target reports operating income | Target's operating margin 20% earns a higher margin score than peers' net margins 5% | Select one common definition rather than rewarding a different reported numerator |
| FCF -20 and net income -10 | Cash conversion +200%, maximum cash-conversion points versus 100% | Treat nonpositive earnings separately; cash burn is not strong conversion |
| Revenue 100 in 2022, 121 in 2024 | 21% growth compared with annual peer growth | Track period length; do not silently annualize without a defined rule |
| Annual and quarter-duration facts in annual filings | Quarterly value can replace annual value | Select duration from start/end, not FY filing labels alone |
| Current debt 100, noncurrent debt 900, same period/filing | Parsed debt 100 | Combine the distinct matched components when this debt burden is intended |
| March assets and December liabilities in one calendar year | One current ratio computed from different dates | Require the same balance-sheet date |
| Two revisions of the same generic annual period | One revision compared with the other as growth | Select one eligible revision per fiscal period |
| Numeric string `NaN` | Accepted, receives maximum relative points, can break JSON serialization | Require finite numbers before calculating ratios or points |
| Same target, one later peer becomes unavailable | Direction grade 100 to 0 as grading switches target | Freeze the outcome definition; report insufficient evidence when necessary |
| Target last on fundamentals, strong industry and related-company support | Overall positive 67.3 while ranked 5/5 | General outlook and peer outperformance are different forecast targets; align the saved thesis and evaluation |
| Thirty repeated calibration records, one company, two models | Validation flag passes with no holdout | Separate models and distinct economic observations; require untouched validation evidence |
| All companies tied | Valid rank 1 and full 8-point bonus | Identify ties and justify bonus policy; rank itself is not mathematically invalid |

Positive controls: SEC historical requests excluded facts filed after the
requested as-of date, and evaluation preserved the original prediction's
baseline, score and thesis. The generic missing-filing-date fallback remains a
historical-availability limitation; do not misreport it as proof that SEC's
explicit filing-date filter is absent. The 96-point ceiling is an allocation
inconsistency, not measured evidence of inaccurate forecasts.

The affected software suites passed 197 regression tests in this audit. These
regressions establish compatibility, not financial validity or forecast accuracy.

## Verification entry points

Run application tests with a temporary writable `DATA_DIR` and
`CONFIG_PATH=config.example.yaml` so imports do not initialize production data.
Relevant suites are `tests/test_main_independence.py`,
`tests/test_providers_cache.py`, `tests/test_local_portfolio.py`,
`tests/test_company_report_check_history.py`, and
`tests/test_company_outlook_evaluation_frontend.py`. Existing passing tests do
not establish financial validity; add regressions for the known counterexamples.

For each revision, verify zero/missing/negative inputs, unequal fiscal periods,
restated filings, tied ranks, one-company groups, partial peer metrics, exact
component totals, immutable saved predictions, and calibration/holdout leakage.

Primary methodological references:

- [SEC EDGAR API: periods and filing data](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [CFA Institute: financial analysis and industry-specific ratios](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/financial-analysis-techniques)
- [CFA Institute: backtesting, walk-forward evaluation and bias](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation)
