---
name: company-report-industry-outlook
description: Analyze public company financial reports against same-industry peers and related industries, using report numbers, peer ranking, future-risk signals, Mermaid relation diagrams with at most three feedback loops, prediction history/accuracy tracking, simple wording, final conclusions, and 0-100 scores. Use when Codex is asked to build, enhance, or perform company finance-report analysis, industry outlook comparison, peer scoring, supplier/customer/related-sector impact analysis, prediction scorecards, or Mermaid diagrams for investment research workflows.
---

# Company Report Industry Outlook

## Core Output

Produce a report-backed industry outlook that answers:

- Which company looks better than peers in the same industry?
- Does the whole industry show future issues or tailwinds?
- Which related industries can affect the target company?
- Will the target company likely benefit or be hurt versus peers?
- What is the final score and plain-language conclusion?
- How accurate were earlier predictions after later reports became available?

Always combine narrative with numbers from company reports. Do not make an outlook from headlines or opinions alone.

## Workflow

1. Identify the target company, ticker, reporting currency, fiscal year, exchange, industry, and sector.
2. Collect source reports for the target company and same-industry peers.
   - Prefer annual reports, 10-K/20-F filings, official investor relations reports, or provider fundamentals backed by filings.
   - Use the latest available annual period and at least 3 years when available.
   - If the user asks for latest/current data, verify online and cite sources.
3. Select peers.
   - Prefer companies with the same industry classification.
   - If same-industry peers are unavailable, use same-sector peers and mark the peer set as weaker.
   - Keep peer comparison focused: 3-8 peers is usually enough.
4. Identify related industries that affect the target.
   - Include supplier/input industries, customer-demand industries, substitute/complement industries, and capital/regulatory dependencies when material.
   - Read reports or fundamentals from representative companies in those related industries when the user asks for affected-industry analysis.
5. Normalize finance numbers before scoring.
   - Use revenue growth, gross/operating/net margin, net income growth, free cash flow trend, debt burden, capex intensity, backlog/deferred revenue, and guidance only when available.
   - Adjust judgment for acquisition-driven growth, FX effects, discontinued operations, restructuring charges, and other one-time items when reports disclose them.
   - Record missing metrics explicitly instead of inventing them.
6. Score the target, peers, industry, and related-industry effect.
   - Read [scoring-and-diagram.md](references/scoring-and-diagram.md) before implementing or producing the scoring model.
   - For the portfolio-analyzer app, first read [the implemented formula and review guide](references/portfolio-analyzer-formula.md). It records the active model version, exact equations and limits, missing-data behavior, known defects, and recheck sequence. Keep it aligned with code whenever a formula or evaluation rule changes; distinguish implemented behavior from proposed improvements.
7. Save prediction history when building an app feature.
   - Store the score, direction, thesis, source reports, baseline financial numbers, horizon date, and later actual results.
   - Compare predictions against future reports to measure model accuracy.
8. Produce a Mermaid diagram.
   - Use a professional `flowchart LR` or `flowchart TD`.
   - Include report numbers in node labels where they fit.
   - Use at most 3 feedback loops/cycles. Collapse extra loops into grouped nodes.
9. End with simple words and a final conclusion.
   - State the best company, target rank, industry outlook, related-industry effect, final score, and confidence.

## Required Report Fields

For each company, extract these when available:

- Revenue and revenue growth.
- Gross margin, operating margin, and net margin.
- Net income and net income growth.
- Operating cash flow, capex, and free cash flow.
- Debt, cash, interest expense, and debt pressure.
- ROIC/ROE/ROA when available, especially for capital-heavy industries.
- Share count and dilution when material.
- Organic growth vs acquisition/FX-driven growth when disclosed.
- Segment revenue/profit if it explains industry exposure.
- Management guidance or risk-factor themes, clearly labeled as qualitative.

Minimum viable analysis can use revenue, net income, margin, and growth. Mark all missing fields.

## Statement-Level Evidence

Treat the annual report as three connected statements, not a single revenue
series:

- **Income statement:** revenue, gross profit, operating income, net income,
  margin movement, and material one-off charges.
- **Cash-flow statement:** operating cash flow, capital expenditure, free cash
  flow, cash conversion, and working-capital movements where reported.
- **Balance sheet:** cash, current assets and liabilities, debt, interest
  burden, receivables, inventory, and material liquidity pressure.

Use statement-derived ratios only when numerator and denominator come from the
same reported period. Compare them to a same-industry peer median. Do not
invent values where an XBRL concept is not filed; lower confidence and name the
missing statement evidence instead.

## Peer And Industry Judgment

Compare the target against peers on:

- Growth: revenue and profit are improving faster than the peer median.
- Profit quality: margins are higher or more stable than peers.
- Cash quality: free cash flow supports growth.
- Balance sheet: debt and interest burden are manageable.
- Capital efficiency: ROIC or return metrics exceed cost-of-capital pressure when available.
- Accounting quality: earnings are not mostly one-time gains, accounting changes, or working-capital pulls.
- Industry health: peer median growth and margins show expansion, stability, or stress.
- Related-industry effect: suppliers/customers/complements show demand support or pressure.

Do not claim certainty about the future. Use wording like `appears better positioned`, `has weaker report signals`, or `industry reports suggest pressure`.

## Deliverable Shape

Use this structure unless the user asks for another format:

1. **Data Used**: companies, fiscal years, source status, missing data.
2. **Peer Table**: company, industry, latest revenue, revenue growth, net margin, net income growth, FCF if available, score.
3. **Industry Outlook**: peer median numbers, issues/tailwinds, confidence.
4. **Related Industry Impact**: relation, representative companies, report numbers, benefit/harm signal.
5. **Mermaid Diagram**: professional relation diagram, max 3 loops.
6. **Simple Words**: short explanation a non-finance reader can understand.
7. **Prediction Memory**: saved prediction id, horizon date, and how future accuracy will be measured when relevant.
8. **Final Conclusion**: best company, target rank, score, confidence, main reason.

## Implementation Notes For Apps

When adding this to a dashboard or API:

- Keep credentials server-side.
- Cache fetched reports/fundamentals.
- Return structured JSON: `companies`, `industry`, `related_industries`, `graph`, `mermaid`, `score`, `conclusion`, `missing`, `provider_status`, `prediction_record`.
- Render the Mermaid text separately from the numeric tables so users can inspect both.
- Store source URLs and fiscal dates with every metric.
- Save prediction history locally with baseline numbers and later actuals.
- Show prediction accuracy by symbol, industry, model version, and horizon.
- Make missing-data states visible in the UI.
- Never tune scores silently. If historical accuracy changes weights, show the old weights, new weights, sample size, and before/after accuracy.

## Prediction History

When implementing learning/accuracy features, store each prediction as a first-class local record:

- Prediction metadata: id, symbol, company name, created date, horizon date, model/version, score, label, direction, confidence.
- Baseline report numbers: fiscal date, revenue growth, net income growth, margins, FCF, leverage, and peer medians used in the prediction.
- Thesis: short reason for the prediction and the related-industry assumptions.
- Diagram snapshot: Mermaid text or graph JSON used at prediction time.
- Actual results: later fiscal date, actual growth/margin/FCF/leverage, actual direction, accuracy score, evaluation text.

Do not call this machine learning unless the implementation actually trains a model. For a deterministic dashboard, call it `prediction tracking`, `accuracy history`, or `model scorecard`.

## Large-Universe Backtesting

When the requested universe is larger than a focused peer group, such as 50-200
S&P 500 constituents, run it as controlled batches rather than as one opaque
job.

1. Build a dated, source-backed constituent list. Record the list date and the
   source because index membership changes over time.
2. Divide the universe into batches of at most 10 companies. Keep peers within
   the same comparable industry cohort; do not compare banks, retailers, and
   semiconductor companies in one peer median.
3. For every batch, create the prediction using only filings available on the
   selected as-of date, save the exact baseline, and then evaluate only against
   reports available by the selected horizon date.
4. Review each completed batch before starting the next one. The review must
   show sample size, evaluated/pending/inconclusive counts, mean accuracy,
   direction confusion counts, and accuracy by industry and confidence.
5. Reserve an untouched holdout set before any tuning. Use earlier batches for
   calibration and later batches for validation. Never change thresholds after
   seeing a holdout result and then report that result as independent.
6. Promote a revised deterministic score rule only when it improves the
   pre-declared calibration measure and also meets the validation gate on the
   untouched holdout. Record old/new model versions, weights or thresholds,
   sample size, and before/after accuracy.
7. Stop and report the evidence when the target is not met. Do not force a
   75% result by relabeling neutral outcomes, removing misses, or selecting a
   favorable horizon after the fact.

Batch API output should include `batch_id`, `batch_number`, `phase`
(`calibration` or `holdout`), symbols attempted, individual predictions,
evaluation results, and a `review` object. The review is an audit record, not
permission to self-tune on the same batch.

## Finance Professional Review Checklist

Before finalizing an analysis or implementation, check:

- Sources: company reports and fiscal dates are attached to every metric.
- Comparability: peer fiscal years, currencies, accounting standards, and one-off adjustments are handled.
- Quality: cash flow and balance sheet signals support or challenge earnings.
- Industry: peer medians are shown separately from target company results.
- Related industries: supplier/customer/complement effects are supported by representative report numbers.
- Diagram: Mermaid syntax is valid, node labels include key numbers, and feedback loops are capped at 3.
- Score: component scores add to the final score and missing data lowers confidence.
- Prediction history: saved prediction records can be evaluated later without changing the original thesis.
