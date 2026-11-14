/* portfolio-risk-v3: signed, common-scenario capital-loss severity.
 * Pure calculation; no network, storage or application state. See the maintained
 * portfolio-risk.md contract. Scenario sizes are assumptions, not probabilities.
 */
(function (root, factory) {
  const estimate = typeof module === "object" && module.exports ? require("./stress-risk-estimate.js") : root.PortfolioStressEstimate;
  const api = factory(estimate);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PortfolioStressRisk = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (estimate) {
  "use strict";
  const MODEL = "portfolio-risk-v3";
  const PROVISIONAL_MODEL = "portfolio-risk-provisional-v2";
  const BUCKETS = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"];
  const SPREAD = [.005, .0075, .01, .015, .03, .05, .08];
  const COUNTRY = [
    { equity: -.35, spread: .01, fx: -.10 }, { equity: -.35, spread: .015, fx: -.10 },
    { equity: -.40, spread: .02, fx: -.15 }, { equity: -.45, spread: .03, fx: -.20 },
    { equity: -.55, spread: .05, fx: -.25 }, { equity: -.65, spread: .08, fx: -.35 },
    { equity: -.75, spread: .12, fx: -.50 },
  ];
  const GLOBAL = [
    { name: "recession", equity: -.40, curve: -.01, spread: 1 },
    { name: "inflation", equity: -.25, curve: .02, spread: .5 },
    { name: "rally", equity: .40, curve: -.02, spread: -1 },
    { name: "fx_only", equity: 0, curve: 0, spread: 0 },
  ];
  const finite = x => typeof x === "number" && Number.isFinite(x);
  const total = xs => xs.reduce((n, x) => n + x, 0);
  const upper = x => String(x || "").trim().toUpperCase();
  const day = x => {
    if (typeof x !== "string" || !/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(x)) return null;
    const value = Date.parse(`${x.slice(0, 10)}T00:00:00Z`);
    return Number.isFinite(value) && new Date(value).toISOString().slice(0, 10) === x.slice(0, 10) ? value : null;
  };
  const years = (date, asOf) => (day(date) - day(asOf)) / (365.25 * 86400000);
  const scoreOf = fraction => Math.round(Math.min(100, Math.max(0, 200 * fraction)));

  function ratingBucket(grade) {
    const g = String(grade || "").trim();
    if (/^(AAA|Aaa)$/i.test(g)) return 0;
    if (/^(AA[+-]?|Aa[123])$/i.test(g)) return 1;
    if (/^(A[+-]?|A[123])$/i.test(g)) return 2;
    if (/^(BBB[+-]?|Baa[123])$/i.test(g)) return 3;
    if (/^(BB[+-]?|Ba[123])$/i.test(g)) return 4;
    if (/^(B[+-]?|B[123])$/i.test(g)) return 5;
    // Actual/default-ambiguous D/SD/RD/Moody's C needs a distressed model.
    if (/^(CCC[+-]?|CC|Caa[123]|Ca)$/.test(g) || g === "C") return g === "C" ? null : 6;
    return null;
  }

  function calculate(items, options = {}) {
    const base = upper(options.baseCurrency || options.base_currency);
    const asOf = String(options.asOf || options.as_of || new Date().toISOString()).slice(0, 10);
    const gaps = [], assumptions = [], countries = new Map(), prepared = [];
    const sourceOwners = new Map(), missingSources = new Set();
    const identityFacts = new Map();
    let unscopedGaps = false;
    let valuesKnown = true, knownGross = 0, gapCount = 0;
    const sourceItems = Array.isArray(items) ? items : [];
    const normalize = options.normalizeField || ((item, name) => item.holding?.[name]);
    const gap = (code, item, detail = "") => {
      gapCount++;
      const owner = sourceOwners.get(item);
      if (owner) missingSources.add(owner); else unscopedGaps = true;
      const h = item?.holding || {}, m = item?.stress_risk || {};
      const row = { code, symbol: String(h.symbol || ""), security_key: String(m.security_key || ""), account_id: String(h.account_id || "") };
      if (detail) row.detail = detail;
      if (!gaps.some(x => x.code === code && x.security_key === row.security_key && x.symbol === row.symbol && x.account_id === row.account_id && x.detail === detail)) {
        gaps.push(row);
      }
    };
    const assume = (code, item) => {
      const row = { code, symbol: String(item?.holding?.symbol || ""), security_key: String(item?.stress_risk?.security_key || "") };
      if (!assumptions.some(x => x.code === row.code && x.security_key === row.security_key && x.symbol === row.symbol)) assumptions.push(row);
    };
    if (!base || day(asOf) === null) { gap("valuation", null); valuesKnown = false; }

    function selectedRating(row, item, enabled) {
      if (Array.isArray(row)) {
        const choices = row.map(x => selectedRating(x, item, enabled)).filter(x => x !== null);
        return choices.length ? choices.reduce((a, b) => a.bucket > b.bucket ? a : b) : null;
      }
      if (!row || row.status !== "rated" || row.scale !== "global" || row.term !== "long_term" || row.stale === true
          || row.conflicting === true || row.eligible === false || !["issue", "issuer", "sovereign"].includes(row.scope)) return null;
      const bucket = row.rating === "C" && ["sp", "fitch"].includes(row.agency) ? 6 : ratingBucket(row.rating);
      if (bucket === null) return null;
      const manual = row.manual_override === true || row.source_kind === "manual" || row.verification_status === "user_entered" || row.verified === false;
      if (manual && !enabled) return null;
      if (manual) assume("manual_rating", item);
      return { bucket, row, negative: row.negative_signal === true || !row.forward_signal_stale && !row.outlook_stale && row.outlook === "negative"
        || !row.forward_signal_stale && !row.watch_stale && row.watch === "negative" };
    }
    const ratingFor = (primary, estimate, item, enabled) => selectedRating(primary, item, enabled)
      || (enabled ? selectedRating(estimate, item, true) : null);

    function identityFact(item) {
      const m = item?.stress_risk || {};
      if (m.issuer_identity_verified === true && typeof m.issuer_name_key === "string" && m.issuer_name_key.trim()) {
        const id = String(m.issuer_id || ""), strong = /^sec:\d+$/.test(id) ? `sec:${id.slice(4).replace(/^0+(?=\d)/, "")}` : null;
        return { name:m.issuer_name_key, id, strong,
          weak:id === m.issuer_name_key || id === `issuer:${m.issuer_name_key}`,
          jurisdiction:upper(m.issuer_legal_jurisdiction) };
      }
      return null;
    }
    function rememberIdentity(item, depth = 0, seen = new Set()) {
      if (!item || depth > 3 || seen.has(item)) return;
      seen.add(item);
      const m = item?.stress_risk || {}, fact = identityFact(item);
      if (fact) identityFacts.set(item, fact);
      const children = m.lookthrough || m.fund_components || m.parameters?.fund_components;
      if (Array.isArray(children)) for (const child of children) {
        if (child && typeof child === "object") rememberIdentity(child.item || {stress_risk:child.stress_risk || child}, depth + 1, seen);
      }
    }

    function exposures(item, metadata, params, value) {
      const asset = upper(item.holding?.asset_class);
      const raw = metadata.currency_exposures || params.currency_exposures || item.exposure_profile?.currency_exposures;
      const result = {};
      if (Array.isArray(raw)) {
        for (const row of raw) {
          const fraction = row.weight ?? (finite(row.percent) ? row.percent / 100 : null);
          if (!upper(row.currency) || !finite(fraction) || fraction < 0 || fraction > 1) return null;
          result[upper(row.currency)] = (result[upper(row.currency)] || 0) + fraction;
        }
      } else if (raw && typeof raw === "object") {
        for (const [currency, fraction] of Object.entries(raw)) {
          if (!upper(currency) || !finite(fraction) || fraction < 0 || fraction > 1) return null;
          result[upper(currency)] = fraction;
        }
      } else if (metadata.instrument_kind?.endsWith("bond") || params.instrument_kind?.endsWith("bond")) {
        if (upper(item.holding?.currency)) result[upper(item.holding.currency)] = 1;
      } else if (params.assumptions_enabled && !["ETF", "MUTUALFUND"].includes(asset) && upper(item.holding?.currency)) {
        result[upper(item.holding.currency)] = 1;
        assume("quote_currency_proxy", item);
      }
      if (item.exposure_profile?.fx_basis === "unknown" || Math.abs(total(Object.values(result)) - 1) > 1e-8) return null;
      if (item.exposure_profile?.fx_basis === "estimated") {
        if (!params.assumptions_enabled) return null;
        assume("economic_currency_estimate", item);
      }
      return result;
    }

    function includeCountry(target, row) {
      const { countryCode, countryCurrency, countryRating, countryFxRating, item } = row;
      if (!countryRating) return;
      const prior = target.get(countryCode);
      if (prior && prior.currency !== countryCurrency) gap("country_currency", item);
      const fxRating = countryFxRating || countryRating;
      if (!prior || countryFxRating && !prior.fxVerified || Boolean(countryFxRating) === prior.fxVerified && prior.rating.bucket < fxRating.bucket) {
        target.set(countryCode, { rating:fxRating, currency:countryCurrency, fxVerified:Boolean(countryFxRating), item });
      }
    }

    function prepare(item, value, inherited = null, depth = 0, sourceItem = item) {
      sourceOwners.set(item, sourceItem);
      rememberIdentity(item);
      const initialGaps = gapCount;
      const h = item.holding || {}, m = item.stress_risk || {}, p = m.parameters || {};
      const enabled = p.assumptions_enabled === true;
      const kind = p.instrument_kind || m.instrument_kind || (upper(h.asset_class) === "EQUITY" || upper(h.asset_class) === "RSU" ? "equity" : ["ETF", "MUTUALFUND"].includes(upper(h.asset_class)) ? "fund" : "");
      if (upper(h.asset_class) === "BOND" && !["corporate_bond", "sovereign_bond"].includes(kind)
          || ["ETF", "MUTUALFUND"].includes(upper(h.asset_class)) && kind !== "fund"
          || ["EQUITY", "RSU"].includes(upper(h.asset_class)) && kind !== "equity") gap("asset_class", item);
      if (m.error || m.status === "unavailable") gap("parameters_unavailable", item);
      if (!kind) gap(upper(h.asset_class) === "BOND" ? "bond_kind" : "asset_class", item);
      if (m.parameters_stale) gap("parameters_stale", item);
      // User-supplied modelling facts remain explicit estimates until verified.
      if (Object.keys(p).length && (m.parameter_provenance?.verification_status === "user_entered" || m.parameters_verification === "user_entered" || m.verification_status === "user_entered")) {
        if (enabled) assume("user_parameters", item); else gap("parameters_unverified", item);
      }
      if (depth > 3) { gap("fund_lookthrough", item); return; }
      const fx = exposures(item, m, p, value);
      if (!fx && kind !== "fund") gap("fx", item);
      if (kind === "fund") {
        const children = m.lookthrough || m.fund_components || p.fund_components;
        if (!Array.isArray(children) || !children.length) { gap("fund_lookthrough", item); return; }
        const weights = children.map(c => c.weight ?? (finite(c.share_pct) ? c.share_pct / 100 : null));
        if (weights.some(w => !finite(w) || w < 0 || w > 1) || Math.abs(total(weights) - 1) > 1e-8) { gap("fund_lookthrough", item); return; }
        if (m.lookthrough_verified !== true) {
          if (!enabled) { gap("fund_lookthrough", item); return; }
          assume("fund_lookthrough_estimate", item);
        }
        const childStart = prepared.length;
        children.forEach((child, i) => {
          const childItem = child.item || { holding: { ...h, symbol: child.symbol || h.symbol, asset_class: child.asset_class, currency: child.currency || h.currency }, stress_risk: child.stress_risk || child };
          prepare(childItem, value * weights[i], { parent: inherited?.parent || item, fx }, depth + 1, sourceItem);
        });
        // A stated wrapper hedge must agree with the complete child/hedge
        // decomposition; the wrapper's trading currency is not a hedge.
        if (fx) {
          const underlying = {};
          for (const child of prepared.slice(childStart)) for (const [currency, weight] of Object.entries(child.fx)) {
            underlying[currency] = (underlying[currency] || 0) + Math.abs(child.value / value) * weight;
          }
          if ([...new Set([...Object.keys(fx), ...Object.keys(underlying)])]
            .some(currency => Math.abs((fx[currency] || 0) - (underlying[currency] || 0)) > 1e-8)) gap("fund_lookthrough", item);
        }
        return;
      }
      if (!["equity", "corporate_bond", "sovereign_bond", "cash_like"].includes(kind)
          || ["corporate_bond", "sovereign_bond"].includes(kind) && m.requires_recovery_model === true
          || ["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(upper(h.asset_sub_class || h.asset_class))
          || item.exposure_profile?.leverage_type && item.exposure_profile.leverage_type !== "none" && item.exposure_profile.leverage_type !== "unleveraged") gap("unsupported_instrument", item);
      const issuer = m.issuer_id || m.issuer_key || p.issuer_key;
      if (!issuer && kind !== "cash_like") gap("issuer_identity", item);
      const countryCode = upper(m.country?.country_code || m.country_code || p.country_code);
      let countryCurrency = upper(p.country_currency || m.country?.currency || m.country_currency);
      const sovereignBasis = p.sovereign_currency_basis;
      const countryRating = kind === "sovereign_bond"
        ? ratingFor(m.sovereign_ratings?.[sovereignBasis] || m.sovereign_rating,
          m.sovereign_ratings_estimate?.[sovereignBasis] || m.sovereign_rating_estimate, item, enabled)
        : ratingFor(m.country_rating, m.country_rating_estimate, item, enabled);
      const countryFxRating = kind === "sovereign_bond"
        ? ratingFor(m.sovereign_ratings?.foreign_currency || m.country_rating,
          m.sovereign_ratings_estimate?.foreign_currency || m.country_rating_estimate, item, enabled)
        : countryRating;
      if (!countryCode && kind !== "cash_like") gap("country", item);
      if (!countryRating && kind !== "cash_like") gap("country_rating", item);
      if (p.country_basis === "issuer_domicile_proxy" || m.country?.basis === "issuer_domicile_proxy") {
        if (enabled) assume("issuer_domicile_proxy", item); else gap("country_exposure", item);
      }
      let credit = null, price = null, duration = null, spread = null;
      if (kind.endsWith("bond")) {
        const currentInputDate = p.as_of || m.parameter_provenance?.as_of;
        if (day(currentInputDate) === null || day(currentInputDate) > day(asOf)
            || day(asOf) - day(currentInputDate) > 7 * 86400000) gap("parameters_stale", item);
        if (p.plain_nominal_noncallable !== true || m.unsupported_bond === true) gap("bond_terms", item);
        credit = kind === "sovereign_bond"
          ? ratingFor(m.sovereign_rating || m.credit_rating, m.sovereign_rating_estimate || m.credit_rating_estimate, item, enabled)
          : ratingFor(m.credit_rating, m.credit_rating_estimate, item, enabled);
        if (!credit) gap("credit_rating", item);
        if (kind === "sovereign_bond") {
          if (!["local_currency", "foreign_currency"].includes(p.sovereign_currency_basis)) gap("sovereign_currency_basis", item);
          if (credit && credit.row.currency_basis && credit.row.currency_basis !== p.sovereign_currency_basis) gap("sovereign_currency_basis", item);
          if (!countryCurrency && p.sovereign_currency_basis === "local_currency") countryCurrency = upper(h.currency);
        }
        if (finite(p.current_spread_bps) && p.current_spread_bps >= 0) spread = p.current_spread_bps / 10000;
        else gap("current_spread", item);
        if (kind === "corporate_bond" && (!finite(p.country_sensitivity) || p.country_sensitivity < 0 || p.country_sensitivity > 1)) gap("country_sensitivity", item);
        if (p.pricing_model === "zero_coupon_continuous") {
          const maturity = p.maturity_date;
          if (p.zero_coupon_confirmed !== true) gap("bond_terms", item);
          if (day(maturity) === null || !(years(maturity, asOf) > 0)) gap("bond_maturity", item);
          else {
            duration = years(maturity, asOf);
            price = (curve, creditShift) => Math.expm1(-duration * (curve + creditShift));
          }
        } else if (p.pricing_model === "cashflows_continuous") {
          const cf = p.cashflows;
          if (!finite(p.continuous_yield)) gap("bond_yield", item);
          if (!Array.isArray(cf) || !cf.length || cf.some(c => day(c.date) === null || !(years(c.date, asOf) > 0) || !finite(c.amount) || c.amount <= 0)) gap("bond_cashflows", item);
          else if (finite(p.continuous_yield)) {
            const legs = cf.map(c => ({ t: years(c.date, asOf), amount: c.amount }));
            const pv = total(legs.map(c => c.amount * Math.exp(-p.continuous_yield * c.t)));
            duration = total(legs.map(c => c.t * c.amount * Math.exp(-p.continuous_yield * c.t))) / pv;
            if (!(pv > 0) || !finite(pv) || !finite(duration) || !(duration > 0)) gap("bond_yield", item);
            else price = (curve, creditShift) => total(legs.map(c => c.amount * Math.exp(-(p.continuous_yield + curve + creditShift) * c.t))) / pv - 1;
          }
        } else gap("bond_cashflows", item);
      }
      if (!countryCurrency && kind !== "cash_like") gap("country_currency", item);
      if (kind === "cash_like") { gap("unsupported_instrument", item); }
      if (gapCount !== initialGaps) return;
      const row = { item, sourceItem, parent: inherited?.parent || item, value, kind, issuer: String(issuer), countryCode, countryCurrency, fx, credit, countryRating, countryFxRating, price, duration, spread, sensitivity: p.country_sensitivity };
      prepared.push(row);
      includeCountry(countries, row);
      if (inherited && inherited.fx && !fx) gap("fx", item);
    }

    let signedValues = 0;
    for (const item of sourceItems) {
      sourceOwners.set(item, item);
      rememberIdentity(item);
      const raw = item?.holding?.market_value;
      const value = normalize(item, "market_value");
      if (!finite(raw) || !finite(value) || (!value && finite(item?.holding?.quantity) && item.holding.quantity !== 0)) {
        valuesKnown = false; gap("valuation", item); continue;
      }
      signedValues += value;
      knownGross += Math.abs(value);
      if (!value) continue;
      const mark = item.stress_risk?.valuation_date || Object.values(item.price_ranges || {}).map(range => range.current_date).filter(Boolean).sort().at(-1);
      if (!mark) { gap("valuation", item); valuesKnown = false; }
      else if (item.stress_risk?.valuation_stale || day(mark) === null || day(mark) > day(asOf) || day(asOf) - day(mark) > 7 * 86400000) { gap("valuation_stale", item); valuesKnown = false; }
      prepare(item, value);
    }
    // Source acquisition can cover different listings in different batches.
    // An identifier-format difference must not create issuer diversification.
    // Build this crosswalk from captured verified legal identity facts, even
    // when the corresponding position lacks some other model input.
    const legalIssuers = new Map();
    const weakJurisdictions = new Map();
    for (const fact of identityFacts.values()) if (fact.weak && fact.jurisdiction) {
      if (!weakJurisdictions.has(fact.name)) weakJurisdictions.set(fact.name, new Set());
      weakJurisdictions.get(fact.name).add(fact.jurisdiction);
    }
    for (const fact of identityFacts.values()) if (fact.strong) {
      if (!legalIssuers.has(fact.name)) legalIssuers.set(fact.name, new Map());
      const ids = legalIssuers.get(fact.name);
      if (!ids.has(fact.strong)) ids.set(fact.strong, new Set());
      if (fact.jurisdiction) ids.get(fact.strong).add(fact.jurisdiction);
    }
    for (const row of prepared) {
      const fact = identityFacts.get(row.item), ids = fact && legalIssuers.get(fact.name);
      if (!fact) continue;
      if (fact.strong) { row.issuer = fact.strong; continue; }
      if (!fact.weak) continue;
      if (!ids?.size) {
        // Issuer-IR facts and verified profiles use the same proved legal-name
        // identity, even when one source adds the explicit "issuer:" namespace.
        if ((weakJurisdictions.get(fact.name)?.size || 0) > 1) gap("issuer_identity", row.item);
        else row.issuer = fact.name;
        continue;
      }
      const [id, jurisdictions] = ids.entries().next().value;
      if (ids.size !== 1 || jurisdictions.size > 1 || fact.jurisdiction && jurisdictions.size && !jurisdictions.has(fact.jurisdiction)) {
        gap("issuer_identity", row.item);
      } else {
        row.issuer = id;
      }
    }
    let cashAccounts;
    if (Array.isArray(options.cashAccounts)) cashAccounts = options.cashAccounts;
    else {
      const cash = options.cash === undefined ? 0 : options.cash;
      cashAccounts = [{ value: cash, currency: upper(options.cashCurrency || base), account_id: "" }];
      // Compatibility for callers with an aggregate signed cash/debt balance.
      if (finite(options.cashDebt) && options.cashDebt > Math.max(0, -cash)) {
        cashAccounts = [{ value: cash + options.cashDebt, currency: base }, { value: -options.cashDebt, currency: base }];
        gap("cash_currency_breakdown", null);
      }
    }
    if (cashAccounts.some(a => !finite(a.value) || a.value !== 0 && !upper(a.currency))) { gap("cash", null); valuesKnown = false; }
    const knownCash = cashAccounts.filter(a => finite(a.value));
    const cash = total(knownCash.map(a => a.value));
    const debt = total(knownCash.map(a => Math.max(0, -a.value)));
    const positiveCash = total(knownCash.map(a => Math.max(0, a.value)));
    for (const row of prepared) if (row.item.stress_risk?.country_requires_recovery_model === true) {
      const relevant = row.kind !== "sovereign_bond" || row.countryCurrency !== base && (
        prepared.some(position => position.value !== 0 && position.fx[row.countryCurrency] > 0)
        || knownCash.some(account => account.value !== 0 && upper(account.currency) === row.countryCurrency));
      if (relevant) gap("unsupported_instrument", row.item);
    }
    if (![signedValues, cash, knownGross, positiveCash, debt].every(finite)) { valuesKnown = false; gap("valuation", null); }
    const equity = valuesKnown && finite(signedValues + cash) ? signedValues + cash : null;
    const gross = knownGross + positiveCash;
    for (const country of countries.values()) {
      const exposed = prepared.some(p => p.value !== 0 && p.fx[country.currency] > 0)
        || knownCash.some(a => a.value !== 0 && upper(a.currency) === country.currency);
      if (country.currency !== base && exposed && !country.fxVerified) gap("country_rating", country.item, "foreign_currency_fx");
    }
    function assessmentExclusions() {
      const excluded = new Set(missingSources), unsupportedCash = new Set();
      let unscoped = unscopedGaps;
      for (const country of countries.values()) {
        if (country.currency === base || country.fxVerified) continue;
        for (const row of prepared) if (row.fx[country.currency] > 0) excluded.add(row.sourceItem);
        for (const account of knownCash) if (account.value !== 0 && upper(account.currency) === country.currency) {
          unsupportedCash.add(account);
          unscoped = true;
        }
      }
      return { excluded, unsupportedCash, unscoped };
    }
    function inputCoverage() {
      const { excluded, unsupportedCash } = assessmentExclusions();
      const preparedSources = new Set(prepared.map(row => row.sourceItem));
      const coveredSecurities = total(sourceItems.filter(item => preparedSources.has(item) && !excluded.has(item)).map(item => Math.abs(normalize(item, "market_value"))));
      const cashGap = gaps.some(row => ["cash", "cash_currency_breakdown"].includes(row.code));
      const coveredCash = cashGap ? 0 : total(knownCash.filter(account => !unsupportedCash.has(account)).map(account => Math.max(0, account.value)));
      const coveredValue = coveredSecurities + coveredCash;
      return { covered_value_percent: valuesKnown ? (gross ? Math.min(100, coveredValue / gross * 100) : 100) : null,
        complete:gaps.length === 0, covered_value:coveredValue, known_gross_value:gross };
    }
    const coverage = inputCoverage();
    const result = {
      model: MODEL, base_currency: base, source_revision: options.sourceRevision || "", label: options.label || "Portfolio risk", status: gaps.length ? "incomplete" : "ok", score: null,
      estimated_score: null, loss_pct: null, stress_loss: null, worst_scenario: null,
      net_equity: equity, cash_debt: debt, cash_pct: gross ? positiveCash / gross * 100 : 0,
      components: {}, quality_details: [], gaps, assumptions, coverage,
      funding: { cash_debt: debt, positive_cash: positiveCash, gross_short: total(sourceItems.map(i => { const v = normalize(i, "market_value"); return finite(v) ? Math.max(0, -v) : 0; })), cash_credit_scope: "not_modeled" },
      scenarios: [], as_of: asOf,
    };
    result.rating_evidence = prepared.flatMap(p => [
      ...(p.credit ? [{security_key:p.item.stress_risk?.security_key || "",role:"instrument_credit",...p.credit.row}] : []),
      ...(p.countryRating ? [{security_key:p.item.stress_risk?.security_key || "",role:"country_credit",...p.countryRating.row}] : []),
      ...(p.countryFxRating ? [{security_key:p.item.stress_risk?.security_key || "",role:"country_fx",...p.countryFxRating.row}] : []),
    ]);
    if (equity !== null && equity <= 0 && (knownGross > 0 || debt > 0)) {
      return { ...result, score: 100, status: "ok", worst_scenario: "nonpositive_equity", components: { stress_loss: 100 } };
    }
    if (equity === 0 && gross === 0 && !gaps.length) return { ...result, score: 0, loss_pct: 0, stress_loss: 0, components: { stress_loss: 0 }, worst_scenario: "none" };

    const currencies = [...new Set([...prepared.flatMap(p => Object.keys(p.fx)), ...knownCash.map(a => upper(a.currency))].filter(c => c && c !== base))].sort();
    const paths = [{ name: "fixed", fx: {} }];
    for (const [suffix, sign] of [["down", -1], ["up", 1]]) {
      paths.push({ name: `all_foreign_${suffix}`, fx: Object.fromEntries(currencies.map(c => [c, .15 * sign])) });
      currencies.forEach(c => paths.push({ name: `${c}_${suffix}`, fx: { [c]: .15 * sign } }));
    }
    const contributionsByScenario = new Map();
    function evaluateScenarios(downgrade = false, positions = prepared, scenarioCountries = countries, capture = true) {
      const scenarios = [];
      const bucket = rating => Math.min(6, rating.bucket + (downgrade && rating.negative ? 1 : 0));
      const add = (name, local, fx) => {
        let pnl = 0;
        const contributions = [];
        for (const p of positions) {
          const move = local(p), fxMove = total(Object.entries(p.fx).map(([c, w]) => w * (fx[c] || 0)));
          const amount = p.value * ((1 + move) * (1 + fxMove) - 1);
          if (!finite(amount) || 1 + move < 0) { gap("unsupported_instrument", p.item); return; }
          pnl += amount;
          if (!downgrade && capture) contributions.push({item:p.parent,pnl:amount});
        }
        pnl += total(knownCash.map(a => a.value * (fx[upper(a.currency)] || 0)));
        if (!finite(pnl)) { gap("valuation", null); return; }
        scenarios.push({ name, pnl, loss: Math.max(0, -pnl) });
        if (!downgrade && capture) contributionsByScenario.set(name, contributions);
      };
      for (const s of GLOBAL) for (const path of paths) {
        add(`${s.name}:${path.name}`, p => {
          if (p.kind === "equity") return s.equity;
          const widening = SPREAD[bucket(p.credit)] * s.spread;
          return p.price(s.curve, widening < 0 ? Math.max(widening, -p.spread) : widening);
        }, path.fx);
      }
      const issuers = [...new Set(positions.filter(p => p.kind !== "sovereign_bond").map(p => p.issuer))].sort();
      for (const issuer of issuers) {
        add(`issuer_distress:${issuer}`, p => p.issuer !== issuer || p.kind === "sovereign_bond" ? 0 : p.kind === "equity" ? -.60
          : p.price(0, Math.max(.2 / p.duration, 2 * SPREAD[bucket(p.credit)])), {});
        add(`issuer_rally:${issuer}`, p => p.issuer !== issuer || p.kind === "sovereign_bond" ? 0 : p.kind === "equity" ? 1 : p.price(-.02, -p.spread), {});
      }
      for (const [code, country] of [...scenarioCountries].sort(([a], [b]) => a.localeCompare(b))) {
        const shock = COUNTRY[bucket(country.rating)];
        add(`country_crisis:${code}`, p => {
          if (p.countryCode !== code) return 0;
          if (p.kind === "equity") return shock.equity;
          // Local- and foreign-currency sovereign opinions are distinct axes.
          // The common country/FX scenario must never overwrite the credit
          // opinion applicable to this particular sovereign obligation.
          const sovereignShock = p.kind === "sovereign_bond" ? COUNTRY[bucket(p.credit)].spread : null;
          return p.price(0, p.kind === "sovereign_bond" ? sovereignShock : Math.max(SPREAD[bucket(p.credit)], p.sensitivity * shock.spread));
        }, country.currency === base ? {} : { [country.currency]: shock.fx });
      }
      return scenarios;
    }
    result.scenarios = evaluateScenarios();
    result.coverage = inputCoverage();
    const worst = result.scenarios.reduce((a, b) => a.loss >= b.loss ? a : b, { name: "none", loss: 0, pnl: 0 });
    if (gaps.length || !(equity > 0)) {
      result.status = "incomplete";
      result.partial_stress_loss = worst.loss;
      result.partial_worst_scenario = worst.name;
      // Financial loss and source completeness are different dimensions.
      // Preserve strict nulls; automatic estimates use declared asset proxies.
      Object.assign(result, estimate?.estimate ? estimate.estimate(sourceItems, {...options,baseCurrency:base,asOf,normalizeField:normalize}, {
        normalize, prepared, cashAccounts, cashBreakdownUnknown:gaps.some(row=>row.code === "cash_currency_breakdown"),
        spreads:SPREAD, countries:COUNTRY, global:GLOBAL,
        selectRating:(row,item)=>selectedRating(row,item,item.stress_risk?.parameters?.assumptions_enabled === true),
        issuerFor:(item,raw)=>{
          const fact=identityFacts.get(item) || identityFact(item), ids=fact && legalIssuers.get(fact.name);
          if (!fact) return raw || null;
          if (fact.strong) return fact.strong;
          if (!fact.weak) return raw || null;
          if (!ids?.size) return (weakJurisdictions.get(fact.name)?.size || 0) > 1 ? null : fact.name;
          const [id,jurisdictions]=ids.entries().next().value;
          return ids.size !== 1 || jurisdictions.size > 1 || fact.jurisdiction && jurisdictions.size && !jurisdictions.has(fact.jurisdiction) ? null : id;
        },
      }) : {provisional_model:PROVISIONAL_MODEL,provisional_basis:"asset_aware_scenarios",provisional_score:null,
        provisional_loss:null,provisional_net_equity:null,provisional_proxy_gross:null,provisional_assumptions:[],
        provisional_scope:"known_values",provisional_range:{min:0,max:100}});
      result.coverage = inputCoverage();
      return result;
    }
    const lossPct = worst.loss / equity * 100;
    const number = scoreOf(worst.loss / equity);
    result.status = assumptions.length ? "estimate" : "ok";
    result.score = assumptions.length ? null : number;
    result.estimated_score = assumptions.length ? number : null;
    result.stress_loss = worst.loss;
    result.loss_pct = lossPct;
    result.worst_scenario = worst.name;
    result.components = { stress_loss: number };
    const positions = new Map();
    for (const entry of contributionsByScenario.get(worst.name) || []) {
      const holding = entry.item.holding || {}, metadata = entry.item.stress_risk || {};
      const key = [metadata.security_key, holding.symbol, holding.account_id].join("|");
      const existing = positions.get(key) || {security_key:metadata.security_key || "",symbol:holding.symbol || "",account_id:holding.account_id || "",pnl:0,loss_contribution_pct:0};
      existing.pnl += entry.pnl;
      existing.loss_contribution_pct = -existing.pnl / equity * 100;
      positions.set(key, existing);
    }
    result.position_contributions = [...positions.values()];
    if (prepared.some(p => p.credit?.negative || p.countryRating?.negative || p.countryFxRating?.negative)) {
      const cases = evaluateScenarios(true);
      const worstSensitivity = cases.reduce((a, b) => a.loss >= b.loss ? a : b, { name: "none", loss: 0 });
      result.forward_sensitivity = { score: scoreOf(worstSensitivity.loss / equity), loss_pct: worstSensitivity.loss / equity * 100,
        worst_scenario: worstSensitivity.name, assumption: "one_bucket_downgrade" };
    }
    return result;
  }
  return Object.freeze({ MODEL, PROVISIONAL_MODEL, calculate, ratingBucket, parameters: Object.freeze({ buckets: BUCKETS, spread: SPREAD, country: COUNTRY, global: GLOBAL }) });
});
