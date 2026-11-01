---
name: trade-simulation
description: Build or review portfolio-analyzer buy, sell, and short what-if baskets across securities and accounts, including projected cash, exposure, account value, and risk. Use for simulation changes rather than recording actual trades or broker execution.
---

# Trade Simulation

Use the existing dashboard and account ledger as the evidence for a proposed trade basket. Inspect `web/trade-simulator.js`, `web/trade-simulator-ui.js`, the context endpoint in `app/main.py`, and `riskScoreForItems` in `web/app.js` before changing behavior.

## Financial contract

- Simulation is read-only: never call transaction-save endpoints, alter the source ledger, or submit broker orders. Drafts belong to the current authenticated browser session and clear on sign-out/user change.
- Resolve every listing and fetch accounts, transactions, FX, and holding evidence as one version-checked snapshot. Deduplicate lookup requests without collapsing account positions. Reject superseded browser responses on basket edits, source changes, and sign-out.
- Apply rows in order to shared projected cash and quantities per account. A sale cannot exceed the projected long holding or silently open a short. A short cannot coexist with a long in the same account/listing. Buy covers a short first and can cross zero into a long.
- Treat listed RSU shares in Investment accounts as supported shares, using their existing listing identity and the shared equity risk factor. RSU classification alone does not make a holding a derivative or an unvested grant. Preserve the separate rejection of actual option/future subclasses and ESOP trading accounts. Check real imported asset classifications when reproducing unsupported-instrument errors; synthetic EQUITY-only fixtures miss this boundary. Explain unsupported asset classes separately from derivatives.
- Cash changes by `−quantity × execution price − fee` for buys and `+quantity × execution price − fee` for sells/shorts. Fees are explicit, in account currency. Do not invent taxes, borrow costs, interest, automatic currency conversion, or broker eligibility.
- Normalize entered prices using instrument conventions: Israeli prices in agorot and US bond prices in cents divide by 100; ordinary US stock prices are dollars. Saved quotes are already normalized. Keep execution price distinct from the saved valuation quote, and show its actual quote date. Blank execution price uses a dated saved quote; an explicit hypothetical price is identified as user input.
- Net account value is signed securities value plus ledger cash. Gross exposure sums absolute securities values. Show short exposure separately. Short proceeds do not create account equity or establish spendable cash. Available cash remains unknown for shorts or derivatives unless a user-specified, clearly described collateral model is implemented; never imply a model is a verified broker rule.
- Reuse the dashboard's 0–100 risk model and its explainable components. Total risk uses the existing 75% combined-holdings score plus 25% exposure-weighted account-score rule. It is a heuristic, not loss probability, VaR, or maximum loss. Negative cash and unavailable evidence must not yield a reassuring risk score.
- Preserve unknown cash, missing price/date/classification, unknown account attribution, and absent FX as unavailable values; do not coerce them to zero or silently omit them from totals. Keep known account results visible when another account is incomplete. Stale quotes retain their actual dates and a visible warning.
- The current position snapshot includes all ledger dates. Reject simulation in an account containing future-dated security trades and mark its valuation/risk unavailable, while retaining known current cash. Excluding future cash movements alone is insufficient: future purchases can otherwise create fictitious holdings and future full sales can hide existing ones.
- State the total's scope: all managed account cash and securities in the snapshot, including unchanged accounts. Separate pension/fund records and private employee grants are not added to this securities total. Do not describe a liquid-account subtotal as the entire household's wealth.

## Interaction and verification

Keep a dedicated Trade Simulation entry within the existing hierarchical navigation. Let the user add, duplicate, edit, and remove rows across accounts, then calculate the whole basket. Keep numerical fields readable, preserve drafts on error/reopen/language change, and mark results stale after an input/source change. Loading must stay inside the simulator.

Maintain the corresponding Help in `web/index.html` and Hebrew in `web/i18n.js`. Cover account prerequisites, price/fee units, row order, buy-to-cover, short uncertainty, total scope, risk limitations, saved evidence, and retry.

Verify deterministic raw-fixture calculations for repeated securities/accounts, partial/full sales, short/cover, fees, currencies, missing evidence, negative cash, overflow, and no input mutation. Verify stale-response rejection and sign-out privacy, then review desktop/mobile and both languages. Follow the project's engineering triad for independent QA of functional changes; simulation authorization does not authorize deployment.
