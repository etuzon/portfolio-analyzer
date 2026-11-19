# Deferred Features and Bugs

Keep requests here when the user chooses to do them later. This is the project's
shared list for future work across sessions.

## Features

| ID | Short summary |
| --- | --- |
| F-001 | Cash-update history with optional, editable multiline notes. |
| F-002 | Filter the account-value history chart between custom From and To dates. |
| F-003 | Hide unknown outlook/watch labels under credit ratings. |
| F-004 | Improve total/account/security risk, update risk simulators, and validate at least 200 simulation cases. |

### F-001 — Account cash-update history with editable multiline notes

Added: 19/11/2026.

When updating an account's cash balance, the user can optionally add a multiline
note explaining why they made the update. Provide a history list of cash updates
where users can view and edit those notes.

Done when:

- Updating cash works with or without a note.
- Notes support multiple lines and preserve line breaks after saving and reload.
- A cash-update history list shows the associated account, update date, cash
  change, and saved note.
- Users can edit or clear a note from the history list without changing the
  recorded cash adjustment or account balance.
- Notes and edits persist after reload and follow the application's editing
  permissions and active interface language.

### F-002 — Custom date range for the account-value history chart

Added: 19/11/2026.

Add custom From and To date controls to the account-value history chart shown
with account and display-currency filters, including its total-value and cash
series. Let the user view the chart between their selected dates.

Done when:

- Users can select a start date and an end date, displayed as `dd/mm/yyyy`.
- The selected range applies inclusively and consistently to every chart series,
  alongside the existing account and currency filters.
- A start date after the end date is rejected with a clear validation message.
- Users can clear the custom range to view the full available history again.
- An empty range shows a useful no-data state. Controls and messages support
  English and Hebrew, and filtering does not change saved history.

### F-003 — Hide unknown outlook/watch labels under credit ratings

Added: 19/11/2026.

Remove unnecessary `לא ידוע / לא ידוע` (Unknown / Unknown) text beneath the
Moody's, S&P and Fitch credit-rating rows shown in Holdings. Show outlook and
watch details only when meaningful values are available.

Done when:

- Unknown or missing outlook/watch values do not produce visible placeholder
  labels, empty rows, or dangling separators.
- When only one value is known, that value remains visible; when both are known,
  both remain visible with their existing meaning.
- The primary rating or unavailable-rating status remains visible.
- The same display rules apply in Hebrew and English without changing saved
  rating evidence, source dates, or underlying status values.

### F-004 — Company, security, and account risk assessments separate from stress loss

Added: 19/11/2026.

Replace the use of a generic standalone stress-loss score as an assessment of
each company's risk. Keep the existing hypothetical stress calculation as a
separate, clearly labelled measure. Define and validate the new methods before
implementation; the discussion has not approved a new numerical formula.

Context: the existing shared 60% issuer-distress assumption can give different
stocks the same score of 60. An equally weighted account of 100 distinct stocks
can instead show 40 because the assumed market-wide recession dominates. Those
results describe fixed stress scenarios, not company-specific risk assessments
or loss probabilities.

Additional user requirements: a fully concentrated stock position can lose
almost all its value, so 60 must never be presented as a maximum-loss ceiling.
Risk must consider the likelihood of a material loss as well as its magnitude.
The user highlighted options and futures: a position described as 10% of an
account may threaten a larger account loss when that figure represents margin
rather than economic exposure. The meaning of that allocation must be verified.

Done when:

- Company risk assesses dated financial/business evidence: debt and refinancing,
  interest coverage, liquidity, cash flow, profitability, business concentration,
  and relevant sector/country vulnerabilities. Use sector-appropriate methods,
  including specialized treatment for financial businesses.
- Security market, credit, and liquidity risks are identified separately from
  company financial strength. Use instrument-appropriate methods for shares,
  bonds, funds, and derivatives; fund-manager risk is not fund-holdings risk.
- Assess actual economic exposure and supported underlying holdings, including
  credit quality, duration, currency, liquidity, leverage, and contractual
  payoffs. Concentration must be evaluated together with those risks; holding
  one instrument does not by itself imply the risk of holding one stock.
  Instrument classification selects the appropriate analysis, not a preset
  score. Do not hardcode exceptions or scores based on a security's name,
  ticker, or fund label. Lower-risk assessments require supporting evidence;
  missing evidence remains unknown.
- Account risk uses actual position weights and joint behavior, including
  correlations, shared issuers, sectors, countries, currencies, cash, borrowing,
  and liquidity. Do not average company scores or reduce risk solely because
  the account contains more tickers. Recognize overlapping fund exposures where
  supported holdings evidence is available.
- Treat confirmed negative cash as borrowing, with its currency and repayment
  obligations identified; distinguish actual debt from settlement timing or
  incomplete records. Measure leveraged losses against net account equity and
  assess interest costs, rate changes, available collateral, margin calls,
  forced liquidation, and cash needed to meet obligations. Do not substitute an
  arbitrary fixed penalty or count the same debt twice.
- Keep each account's funding shortfall visible even if another account holds
  positive cash. Do not assume that cash is transferable or eligible collateral
  without evidence of access and the relevant broker rules. Missing borrowing
  terms or collateral rules must remain unknown, not an invented margin limit.
- Evaluate historical downside/tail-loss measures, such as expected shortfall,
  alongside severe hypothetical stresses. State the horizon, data window,
  confidence level where applicable, assumptions, and coverage; show account
  losses in money and as a percentage of net equity.
- Assess the likelihood of crossing a chosen material-loss threshold over an
  explicit horizon, alongside tail-loss severity. A 20% account loss is the
  user's example, not an approved universal threshold or calibrated probability.
  Agree the horizon and distinguish loss at the horizon from a drawdown reached
  at any time during it. Stress scenarios alone cannot establish probabilities;
  unsupported probability estimates remain unavailable.
- Include concentrated-stock near-total-loss scenarios and, where contractually
  possible, losses beyond account equity. Preserve monetary losses and uncapped
  loss percentages even if a display index is limited to 0–100.
- For futures and other leveraged positions, distinguish posted margin,
  premium/market value, and notional exposure. Use the actual contracts,
  direction, multipliers, underlying moves, and FX; assess variation-margin
  funding needs and forced-liquidation risk separately from final losses.
- Model option strike, maturity, underlying exposure, volatility sensitivity,
  exercise/assignment, and settlement with the actual payoff. Distinguish fully
  paid long-option premium risk from short-option liabilities and defined-risk
  spreads. Evaluate hedges jointly: protective derivatives can reduce account
  risk, so do not automatically classify every derivative position as high risk.
- Missing evidence remains explicitly unknown or insufficient, without a
  generic company-risk score of 60. Ratings and financial-quality scores must
  not be silently repurposed as comprehensive company risk or loss probability.
- If a 0–100 risk index is used, establish and document its meaning, anchors,
  evidence, and limitations before applying the requested five-color ranges.
- Financial review and independent QA cover controlled no-cash accounts with
  one fully concentrated stock versus 100 genuinely diversified equal-weight
  stocks, repeated holdings of the same issuer, one dominant holding, correlated
  sector exposures, cash, FX, borrowing/negative cash in individual accounts,
  cash held elsewhere without assumed transfers, stock near-total loss, fully paid long
  options, short options, hedged positions, and futures where a small margin
  allocation can generate a materially larger account loss. Do not hardcode
  desired scores or claim that 100 securities are always safer than one.
- Update existing risk simulations, trade/buy/sell/short what-if baskets, and
  risk-reduction alternatives to use the approved new risk methods consistently
  with the live dashboard. Show baseline versus simulated total-portfolio,
  account, and security assessments with their actual units and meanings; keep
  company risk, account exposure, and hypothetical stress loss distinguishable.
- Simulator calculations must include projected holdings, cash/negative cash,
  borrowing, FX, derivative notional/payoffs and supported margin/funding needs,
  and joint hedges. A small margin allocation must not be treated as a limit on
  loss. Freeze the simulation's input dates and model versions; preserve earlier
  saved simulations under their original methods and keep simulations separate
  from real transactions.
- Before acceptance, execute at least 200 distinct, purposeful simulation cases
  covering the risk dimensions above. Check total-portfolio, account, and
  security results in each case where applicable, including expected unavailable
  states. Cover both baseline and simulated before/after outcomes; repeated
  identical inputs or random runs without independent expectations do not satisfy
  the minimum.
- For every simulation case, retain the raw inputs, purpose, expected result or
  expected relationship, actual risk values, units, model version, assumptions,
  and pass/fail explanation. Verify arithmetic, financial plausibility, and
  whether the displayed result helps users understand the relevant risk.
  Include boundary, missing/stale data, ranking, concentration, correlation,
  leverage, derivatives, and funding scenarios with independent financial and
  QA review. Fix and re-test material failures before completion.
- Simulation counts establish scenario and software coverage, not empirical
  accuracy of loss probabilities or forecasts. Validate any predictive claim
  separately with dated historical/out-of-sample evidence and explicit uncertainty.
- Holdings, account summaries, tooltips, sorting, history, and affected consumers
  identify the measure they use. Preserve historical model meanings and update
  affected English/Hebrew Help; financial-model and application versions follow
  their separate project policies.

## Bugs

| ID | Short summary |
| --- | --- |
| — | No deferred bugs recorded. |

## Maintaining this list

Next feature ID: `F-005`. Next bug ID: `B-001`.

- Add an item only when the user defers it or asks to put it on this list.
- Assign the next ID from its category and advance that category's next-ID value.
  Never reuse or renumber IDs, including after completed items are removed.
- Keep separate Features and Bugs summary tables with adjacent `ID` and
  `Short summary` columns. Keep each summary brief and put the full requirements
  below the relevant table, under a heading containing the same ID.
- Give each item a clear title, the date added (`dd/mm/yyyy`), a short description,
  and what must be true for it to be done. For bugs, include known reproduction
  steps and expected versus actual behavior. Mark missing details as unknown.
- Replace the empty-table row when adding the first item. Keep unrelated
  items intact and update an existing item instead of creating duplicates.
- Consult relevant items when starting work. Being listed here does not start
  implementation or authorize a release.
- Remove an item only after its requested work is completed and verified. If
  deployment is part of that request, verify the deployment before removal.
  Partial, blocked, or unverified work stays on the list with its remaining work.
- Remove both the summary row and its matching details when completing an item.
  Restore the empty-table row when the last item in a section is removed.
