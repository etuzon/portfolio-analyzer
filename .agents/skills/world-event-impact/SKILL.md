---
name: world-event-impact
description: Build evidence-backed world-event impact cases and forecasts for stocks, revenue and net income, including regional transmission, conditional probabilities and later outcome evaluation. Use for historical stock-move explanations and comparison with future events.
---

# World event impact

Use the canonical workflow and blank records in `app/workflows/world-event-impact.yaml`, relative to the portfolio-analyzer repository root. The running application exposes the same content through `get_event_impact_workflow` in its assistant read-tool catalog. Read the workflow before analyzing cases.

Read existing curated cases in `app/workflows/cases/` or through `get_event_impact_cases` (optional `symbol` filter) before comparing a new event. These are retrospective examples with source-specific limits, not a representative training cohort. Add explicitly requested reusable cases there as versioned YAML records; preserve source links, calculations, unresolved evidence and selection bias. The assistant can read bundled cases but cannot write them.

For cross-stock comparisons, use the shared `event_id` filter and read `event_patterns` in the response (stored under `app/workflows/patterns/`). Match an event to documented business exposures and transmission channels. Preserve positive and weakly affected comparisons, offsets and conflicting observations. Use aligned sessions and currencies, distinguish ADRs from US-listed ordinary shares, and keep calculated returns separate from vendor-reported percentages when rounded prices disagree. A sector map is a research hypothesis, not a calibrated rule.

Choose the requested mode:

- **Historical case:** verify the user's stock move, event timeline, price window and company exposure. Fill `historical_case`, `source`, `regional_effect` and `metric_outcome` records. A user's explanation remains a hypothesis until supported. Record alternative causes and unresolved evidence.
- **New event:** define the information cutoff and horizons, compare verified analogues and fill `forecast` and `probability` records. Apply the estimation and validation gates. Unsupported estimates stay null with specific missing reasons.
- **Outcome review:** preserve the original forecast and append an `evaluation`. Compare stock returns, revenue and net income independently. Recommend versioned changes only after chronological holdout evaluation.

For the next user-supplied stocks, collect tickers/exchanges, observed dates or windows, reported rise/fall, suspected event and any sources. Investigate available evidence before asking for information that sources can supply. Keep missing fields explicit rather than inventing dates or explanations.

Verify financial and current-event claims using primary sources and available provider abstractions. If tools cannot access those sources, state what remains unverified. An event-study comparison supports association; it does not by itself identify causation.

Use the workflow's separate event, exposure, direction, severity, onset, persistence, recovery, spillover, scenario and joint-loss probabilities. State the conditioning information and time period every time. Keep evidence confidence separate from probability and magnitude. Never substitute the dashboard's heuristic risk score for a loss probability.

For cross-region analysis, trace the supported path from origin through suppliers, customers, substitution, transport, currency, financing or regulation to each destination. Use separate signs, lags and magnitudes for each company and region. Unknown exposure cannot justify a numeric impact.

Generate the report in the user's language with dd/mm/yyyy display dates. Follow the workflow's report structure. Put citations beside factual claims and identify the missing evidence needed for each withheld percentage.

This skill is a research template, not an installed event-monitoring service or trained model. Adding cases is explicit evidence collection and evaluation, not automatic model learning. The in-app assistant is read-only; it cannot save a research library through its tool catalog. When asked to retain cases in the workspace, save explicit dated artifacts to a user-owned research directory and report their paths. Avoid modifying runtime caches, credentials, external import sources or original forecasts.
