---
name: financial-data-quality
description: Audit financial source lineage, publication cutoffs, fiscal periods, units, currencies, security identity, corporate actions, and missing data. Use before trusting financial joins, derived metrics, historical research, or provider normalization.
---

# Financial Data Quality

Treat every observation as a dated, sourced claim with a definition. Distinguish
raw data, normalized values, calculated metrics, and cached aggregates.

- Retain issuer/security identity, exchange, source URL/accession, publication and
  observation dates, retrieval time, currency, unit/scale, period start/end, and
  adjustment basis. Ticker text alone is not a stable global ID.
- Enforce cutoffs on publication time, not only fiscal end. Amendments and
  restatements become eligible once public. Preserve original/revised evidence;
  do not overwrite historical knowledge with later corrections.
- Distinguish flow intervals and balance-sheet instants. Verify actual start/end
  dates and fiscal calendars; matching year labels do not prove comparability.
- Reconcile debt totals/components, capex signs, basic/diluted shares, reported/
  adjusted earnings, and entity/segment scope. Read definitions before substituting
  superficially similar concepts.
- Convert units exactly once. Currency differs from quote convention: distinguish
  shekels/agorot, bond percent-of-par, accrued interest, and normalized saved quotes.
- Match FX date and purpose; balance-sheet and flow conversions can need different
  conventions. Separate native/investor-currency returns. Unknown FX leaves
  affected totals unavailable.
- Maintain a consistent corporate-action basis for prices, dividends, splits,
  spin-offs, rights, and shares. Never splice raw and adjusted price series.
- Separate market/publication time and retrieval/cache time. State staleness and
  coverage. Missing, zero, unavailable, pending, and invalid are distinct; reject
  nonfinite values and inappropriate boolean numerics.
- Trace source edits/deletes through derived metrics, history, caches, APIs, and
  views. Preserve frozen forecast baselines; rebuilding a cache does not authorize
  rewriting a prediction.
- For asynchronous outputs representing current live source state, verify a
  coherent source revision when capturing inputs and when publishing. Cache invalidation alone does
  not stop pre-edit work from repopulating stale cache after an edit; client
  response guards alone do not protect the next reload. Verify server publication
  and client supersession independently against the actual action sequence.
  An explicitly frozen coherent research/simulation snapshot follows its own
  validity contract; later live refreshes do not retroactively invalidate it.

Return lineage, accepted/rejected observations with reasons, normalization rules,
and raw fixtures reproducing meaningful joins/missing inputs. Use maintained
repository models where present; do not silently change formulas or apply a newer
model to historical predictions.

Reference: [SEC financial facts and periods](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
