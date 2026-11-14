/* Asset-aware scenario estimates. Proxy assumptions never replace source facts. */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PortfolioStressEstimate = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  const MODEL = "portfolio-risk-provisional-v2";
  const finite = value => typeof value === "number" && Number.isFinite(value);
  const upper = value => String(value || "").trim().toUpperCase();
  const sum = values => values.reduce((total, value) => total + value, 0);
  const score = fraction => Math.round(Math.min(100, Math.max(0, 200 * fraction)));
  const day = value => {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
    const date = Date.parse(value.slice(0, 10) + "T00:00:00Z");
    return Number.isFinite(date) && new Date(date).toISOString().slice(0, 10) === value.slice(0, 10) ? date : null;
  };

  function treasuryReference(item, asOf) {
    const h = item.holding || {}, reference = item.market_data || {}, security = reference.security || {}, details = reference.details || {};
    const identifier = upper(security.cusip || security.identifier);
    if (reference.provider !== "treasury_direct" || !["ok", "partial"].includes(reference.status)
        || upper(h.currency) !== "USD" || upper(security.currency) !== "USD"
        || security.issuer !== "United States Department of the Treasury"
        || !/^[A-Z0-9]{9}$/.test(identifier) || ![upper(h.symbol), upper(h.secondary_symbol)].includes(identifier)
        || security.kind && security.kind !== "bond"
        || reference.request?.kind && reference.request.kind !== "bond"
        || reference.request?.identifier && upper(reference.request.identifier) !== identifier
        || day(reference.retrieved_at) === null || day(reference.retrieved_at) > day(asOf)) return null;
    try {
      const source = new URL(reference.source_url);
      if (source.protocol !== "https:" || !["treasurydirect.gov", "www.treasurydirect.gov"].includes(source.hostname)) return null;
    } catch { return null; }
    const type = upper(details.security_type).replace(/[\s_-]/g, "");
    const unsupportedPayoff = ["FUND", "MUTUALFUND", "ETF", "OPTION", "DERIVATIVE", "FRN", "FLOATINGRATENOTE", "TIPS", "INFLATIONLINKED"].includes(type)
      || details.floating_rate === true || details.inflation_protected === true
      || details.callable === true || details.noncallable === false || details.plain_nominal_noncallable === false;
    const plainNominalSupported = ["BILL", "NOTE", "BOND"].includes(type)
      && details.floating_rate === false && details.inflation_protected === false && !unsupportedPayoff;
    return {maturity_date:day(details.maturity_date) !== null ? details.maturity_date : null,
      unsupported_payoff:unsupportedPayoff,
      plain_nominal_supported:plainNominalSupported,
      reference_facts:{identifier, issuer:security.issuer, currency:security.currency,
        security_type:details.security_type || null, floating_rate:details.floating_rate ?? null,
        inflation_protected:details.inflation_protected ?? null, callable:details.callable ?? null,
        noncallable:details.noncallable ?? null,
        coupon_rate_pct:finite(details.coupon_rate_pct) ? details.coupon_rate_pct : null},
      source_url:reference.source_url, reference_retrieved_at:reference.retrieved_at};
  }

  function estimate(items, options, context) {
    const base = upper(options.baseCurrency || options.base_currency);
    const asOf = String(options.asOf || options.as_of).slice(0, 10);
    const rows = [], assumptions = [], proxyRoots = new Set();
    let wholeScope = Boolean(base && day(asOf) !== null), securities = 0, gross = 0;
    const addAssumption = (code, item, details = {}, root = item) => {
      const row = {code, security_key:item?.stress_risk?.security_key || "", symbol:item?.holding?.symbol || "", ...details};
      if (!assumptions.some(old => JSON.stringify(old) === JSON.stringify(row))) assumptions.push(row);
      if (root) proxyRoots.add(root);
    };
    const selected = (raw, item) => context.selectRating(raw, item);
    const fxFor = (item, root) => {
      const m = item.stress_risk || {}, p = m.parameters || {}, profile = item.exposure_profile || {};
      const raw = m.currency_exposures || p.currency_exposures || profile.currency_exposures;
      const output = {};
      if (Array.isArray(raw)) for (const entry of raw) {
        const weight = entry.weight ?? (finite(entry.percent) ? entry.percent / 100 : null);
        if (!upper(entry.currency) || !finite(weight) || weight < 0 || weight > 1) return null;
        output[upper(entry.currency)] = (output[upper(entry.currency)] || 0) + weight;
      }
      else if (raw && typeof raw === "object") for (const [currency, weight] of Object.entries(raw)) {
        if (!upper(currency) || !finite(weight) || weight < 0 || weight > 1) return null;
        output[upper(currency)] = weight;
      }
      if (Object.keys(output).length) {
        if (Math.abs(sum(Object.values(output)) - 1) > 1e-8) return null;
        if (profile.fx_basis === "unknown" || profile.fx_basis === "estimated") addAssumption("quote_currency_proxy", item, {currency_exposures:output}, root);
        return output;
      }
      const currency = upper(profile.fx_reference_currency || item.holding?.currency);
      if (!currency) return null;
      addAssumption("quote_currency_proxy", item, {currency}, root);
      return {[currency]:1};
    };
    function build(item, value, root = item, depth = 0) {
      if (!item || depth > 3 || !finite(value)) return false;
      if (!value) return true;
      const h = item.holding || {}, m = item.stress_risk || {}, p = m.parameters || {}, profile = item.exposure_profile || {};
      const asset = upper(h.asset_class), subtype = upper(h.asset_sub_class), focus = profile.asset_focus;
      const parametersUsable = ![m.parameters_verification, m.parameter_provenance?.verification_status, m.verification_status].includes("user_entered") || p.assumptions_enabled === true;
      if (["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(subtype || asset)
          || focus === "derivative" || m.unsupported_bond === true
          || parametersUsable && (asset === "BOND" || String(p.instrument_kind || m.instrument_kind || "").endsWith("bond")) && p.plain_nominal_noncallable === false
          || profile.leverage_type && !["none", "unleveraged"].includes(profile.leverage_type)) {
        addAssumption("unknown_asset_proxy", item, {}, root);
        return false;
      }
      const kind = p.instrument_kind || m.instrument_kind || "";
      const fundClasses = ["ETF", "FUND", "MUTUALFUND", "MUTUAL_FUND", "MONEY_MARKET_FUND", "BOND_FUND", "EQUITY_FUND"];
      const fundAsset = fundClasses.includes(asset) || fundClasses.includes(subtype);
      // A fund-only focus cannot erase an actual share's issuer exposure.
      const equity = !fundAsset && (["EQUITY", "RSU"].includes(asset) || kind === "equity");
      const directBond = !fundAsset && !equity && (asset === "BOND" || kind.endsWith("bond"));
      const governmentReference = directBond ? treasuryReference(item, asOf) : null;
      const referenceCountryMatches = !governmentReference || upper(m.country?.country_code || m.country_code || p.country_code) === "US";
      if (governmentReference?.unsupported_payoff) {
        addAssumption("unknown_asset_proxy", item, {...governmentReference}, root); return false;
      }
      if (governmentReference?.maturity_date && day(governmentReference.maturity_date) <= day(asOf)) {
        addAssumption("unknown_asset_proxy", item, {}, root); return false;
      }
      const fundFocus = ["money_market", "government_bond", "investment_grade_bond", "high_yield_bond", "broad_equity", "sector_equity", "single_country_equity"].includes(focus);
      const fund = !equity && !directBond && (fundAsset || kind === "fund" || kind === "money_market"
        || ["", "UNKNOWN"].includes(asset) && fundFocus);
      const eligibleOpinions = raw => (Array.isArray(raw) ? raw : [raw]).filter(row => {
          if (!row || row.status !== "rated" || row.scale !== "global" || row.term !== "long_term"
              || row.stale || row.conflicting || row.eligible === false || !["issue", "issuer", "sovereign"].includes(row.scope)) return false;
          const manual = row.manual_override || row.source_kind === "manual" || row.verification_status === "user_entered" || row.verified === false;
          if (manual && p.assumptions_enabled !== true) return false;
          if ([row.rating_date, row.fetched_at].some(date => day(date) !== null && day(date) > day(asOf))) return false;
          return true;
        });
      const recoveryGrade = row => row.agency === "sp" && ["D", "SD"].includes(row.rating)
        || row.agency === "fitch" && ["D", "RD"].includes(row.rating)
        || row.agency === "moodys" && row.rating === "C";
      const usableOpinions = raw => eligibleOpinions(raw).filter(row => recoveryGrade(row) || selected(row, item));
      const recoveryOpinion = raw => {
        const eligible = usableOpinions(raw);
        const issues = eligible.filter(row => row.scope === "issue");
        return (issues.length ? issues : eligible).some(recoveryGrade);
      };
      const directSovereign = directBond && (kind === "sovereign_bond" || Boolean(governmentReference));
      const referenceIssues = governmentReference ? [...usableOpinions(m.credit_rating), ...usableOpinions(m.sovereign_rating)]
        .filter(row => row.scope === "issue") : [];
      const referenceLocal = governmentReference && referenceCountryMatches
        ? [...usableOpinions(m.sovereign_ratings?.local_currency), ...usableOpinions(m.sovereign_rating)]
          .filter(row => row.scope === "sovereign" && row.currency_basis === "local_currency") : [];
      const referenceCredit = referenceIssues.length ? referenceIssues : referenceLocal;
      if (directBond && (m.requires_recovery_model === true || recoveryOpinion(directSovereign
          ? governmentReference ? referenceCredit : m.sovereign_rating || m.sovereign_ratings?.[p.sovereign_currency_basis] : m.credit_rating))) {
        addAssumption("recovery_model_required", item, {}, root);
        return false;
      }
      const children = m.lookthrough || m.fund_components || p.fund_components;
      if (fund && m.lookthrough_verified === true && Array.isArray(children) && children.length) {
        const weights = children.map(child => child.weight ?? (finite(child.share_pct) ? child.share_pct / 100 : null));
        if (weights.every(weight => finite(weight) && weight >= 0 && weight <= 1) && Math.abs(sum(weights) - 1) < 1e-8) {
          const before = rows.length;
          const valid = children.map((child, index) => build(child.item || {holding:{...h, symbol:child.symbol || h.symbol,
            asset_class:child.asset_class, currency:child.currency || h.currency}, stress_risk:child.stress_risk || child}, value * weights[index], root, depth + 1)).every(Boolean);
          if (valid) {
            const rawWrapper = m.currency_exposures || p.currency_exposures || profile.currency_exposures;
            if (rawWrapper && (Array.isArray(rawWrapper) ? rawWrapper.length : Object.keys(rawWrapper).length)) {
              const wrapper = fxFor(item, root), underlying = {};
              for (const row of rows.slice(before)) for (const [currency, weight] of Object.entries(row.fx)) underlying[currency] = (underlying[currency] || 0) + Math.abs(row.value / value) * weight;
              if (!wrapper || [...new Set([...Object.keys(wrapper), ...Object.keys(underlying)])].some(currency => Math.abs((wrapper[currency] || 0) - (underlying[currency] || 0)) > 1e-8)) {
                rows.splice(before); return false;
              }
            }
            return true;
          }
          rows.splice(before);
          return false;
        }
      }
      const fx = fxFor(item, root);
      if (!fx) return false;
      const moneyMarket = fund && (focus === "money_market" || kind === "money_market"
        || asset === "MONEY_MARKET_FUND" || subtype === "MONEY_MARKET_FUND");
      const sovereign = fund ? focus === "government_bond"
        : directBond && (directSovereign || kind !== "corporate_bond" && focus === "government_bond");
      const bond = directBond || fund && (asset === "BOND_FUND" || subtype === "BOND_FUND"
        || ["government_bond", "investment_grade_bond", "high_yield_bond"].includes(focus));
      if (!moneyMarket && !bond && !equity && !fund) {
        addAssumption("unknown_asset_proxy", item, {}, root); return false;
      }
      const countryBasis = governmentReference ? "economic_exposure" : p.country_basis || m.country?.basis;
      const underlyingCountry = !fund || countryBasis === "economic_exposure";
      const declaredCountryCode = upper(m.country?.country_code || m.country_code || p.country_code);
      const countryCode = governmentReference ? "US" : underlyingCountry ? declaredCountryCode : "";
      const declaredCountryCurrency = governmentReference ? "USD" : underlyingCountry && (p.country_currency || m.country?.currency || m.country_currency);
      const countryCurrency = upper(declaredCountryCurrency || profile.fx_reference_currency || h.currency);
      const countryRatingMatches = referenceCountryMatches;
      const country = countryCode && countryRatingMatches ? selected(m.sovereign_ratings?.foreign_currency || m.country_rating, item) : null;
      const countryRecovery = Boolean(countryCode && countryRatingMatches && (m.country_requires_recovery_model === true
        || recoveryOpinion(m.sovereign_ratings?.foreign_currency || m.country_rating)));
      if (countryRecovery && !directSovereign) {
        addAssumption("recovery_model_required", item, {}, root);
        return false;
      }
      if (!country || !countryCode || countryBasis === "issuer_domicile_proxy" || !declaredCountryCurrency) {
        addAssumption("country_stress_proxy", item, {currency:countryCurrency,
          basis:!countryCode ? "generic_country_proxy" : countryBasis === "issuer_domicile_proxy" ? countryBasis
            : !declaredCountryCurrency ? "quote_currency_proxy" : "generic_country_proxy"}, root);
      }
      const row = {item, root, value, fx, moneyMarket, fund, sovereign, directSovereign, equity:equity || !bond && !moneyMarket,
        sector:fund && focus === "sector_equity",
        countryCode, countryCurrency, country, countryRecovery, issuer:null, credit:null, price:null, duration:null, spread:0};
      const exact = context.prepared.find(prepared => prepared.item === item);
      if (moneyMarket) {
        addAssumption("money_market_proxy", item, {loss_fraction:.01, source_date:profile.as_of,
          ...(profile.source_url ? {source_url:profile.source_url} : {})}, root);
      } else if (row.equity) {
        if (fund) addAssumption(row.sector ? "sector_fund_proxy" : "equity_fund_proxy", item, {loss_fraction:row.sector ? .5 : .4}, root);
      } else {
        // A wrapper's issuer opinion and cashflows do not describe its holdings.
        const sovereignBasis = governmentReference ? "local_currency" : p.sovereign_currency_basis;
        row.credit = fund ? null : governmentReference ? selected(referenceCredit, item)
          : exact?.credit || selected(sovereign ? m.sovereign_rating || m.credit_rating : m.credit_rating, item);
        if (sovereign && row.credit?.row.scope !== "issue" && !["local_currency", "foreign_currency"].includes(sovereignBasis)) row.credit = null;
        if (sovereign && row.credit?.row.currency_basis && sovereignBasis
            && row.credit.row.currency_basis !== sovereignBasis) row.credit = null;
        row.widening = row.credit ? context.spreads[row.credit.bucket] : focus === "high_yield_bond" ? .05
          : focus === "investment_grade_bond" ? .015 : sovereign ? .02 : .025;
        if (!row.credit) addAssumption("unrated_credit_proxy", item, {spread_bps:row.widening * 10000}, root);
        const pricingDate = day(p.as_of || m.parameter_provenance?.as_of);
        const currentPricing = pricingDate !== null && pricingDate <= day(asOf) && day(asOf) - pricingDate <= 7 * 86400000;
        if (!fund && exact?.price) { row.price = exact.price; row.duration = exact.duration; }
        else if (!fund && parametersUsable && p.pricing_model === "zero_coupon_continuous" && p.plain_nominal_noncallable === true
            && p.zero_coupon_confirmed === true && m.unsupported_bond !== true && day(p.maturity_date) !== null && day(p.maturity_date) > day(asOf)) {
          row.duration = (day(p.maturity_date) - day(asOf)) / (365.25 * 86400000);
          row.price = (curve, spread) => Math.expm1(-row.duration * (curve + spread));
        } else if (!fund && parametersUsable && currentPricing && p.pricing_model === "cashflows_continuous" && p.plain_nominal_noncallable === true
            && m.unsupported_bond !== true && finite(p.continuous_yield) && Array.isArray(p.cashflows) && p.cashflows.length
            && p.cashflows.every(flow => day(flow.date) !== null && day(flow.date) > day(asOf) && finite(flow.amount) && flow.amount > 0)) {
          const legs = p.cashflows.map(flow => ({amount:flow.amount, years:(day(flow.date) - day(asOf)) / (365.25 * 86400000)}));
          const pv = yieldValue => sum(legs.map(flow => flow.amount * Math.exp(-yieldValue * flow.years)));
          const initial = pv(p.continuous_yield);
          row.duration = sum(legs.map(flow => flow.years * flow.amount * Math.exp(-p.continuous_yield * flow.years))) / initial;
          if (finite(initial) && initial > 0 && finite(row.duration) && row.duration > 0) row.price = (curve, spread) => pv(p.continuous_yield + curve + spread) / initial - 1;
          else return false;
        } else {
          row.duration = focus === "high_yield_bond" ? 4 : 5;
          const verifiedMaturity = ![m.parameters_verification, m.parameter_provenance?.verification_status, m.verification_status].includes("user_entered")
            && [m.parameters_verification, m.parameter_provenance?.verification_status].includes("verified");
          const referenceMaturity = governmentReference?.plain_nominal_supported ? governmentReference.maturity_date : null;
          const maturity = !fund && (referenceMaturity || parametersUsable && verifiedMaturity
            && p.plain_nominal_noncallable === true && p.maturity_date);
          if (day(maturity) !== null && day(maturity) > day(asOf)) {
            const remaining = (day(maturity) - day(asOf)) / (365.25 * 86400000);
            if (remaining < row.duration) {
              row.duration = remaining;
              addAssumption("bond_duration_maturity_bound", item, {
                ...(referenceMaturity ? governmentReference : {source_url:p.source_url || m.parameter_provenance?.source_url}),
                duration_years:remaining, maturity_date:maturity}, root);
            }
          }
          row.price = (curve, spread) => Math.expm1(-row.duration * (curve + spread));
          addAssumption("bond_duration_proxy", item, {duration_years:row.duration}, root);
        }
        if (governmentReference) addAssumption("government_bond_proxy", item, {...governmentReference,
          currency:"USD", duration_years:row.duration, spread_bps:row.widening * 10000}, root);
        if (fund) addAssumption("bond_fund_proxy", item, {duration_years:row.duration, spread_bps:row.widening * 10000}, root);
        if (!fund && parametersUsable && finite(p.current_spread_bps) && p.current_spread_bps >= 0 && currentPricing) row.spread = p.current_spread_bps / 10000;
        else addAssumption("credit_tightening_omitted", item, {}, root);
        const declaredSensitivity = !fund && parametersUsable && finite(p.country_sensitivity)
          && p.country_sensitivity >= 0 && p.country_sensitivity <= 1;
        row.sensitivity = declaredSensitivity ? p.country_sensitivity : 1;
        if (!declaredSensitivity) addAssumption("country_sensitivity_proxy", item, {}, root);
      }
      if (!fund && !moneyMarket && !sovereign) {
        row.issuer = context.issuerFor(item, exact?.issuer || m.issuer_id || m.issuer_key || p.issuer_key);
        if (!row.issuer) {
          row.issuer = "security:" + (m.security_key || [h.symbol, h.stock_market, h.currency].map(upper).join("|"));
          addAssumption("security_key_issuer_proxy", item, {}, root);
        }
      }
      rows.push(row);
      return true;
    }
    const values = new Map();
    for (const item of items) {
      const value = context.normalize(item, "market_value"), raw = item.holding?.market_value;
      const mark = item.stress_risk?.valuation_date || Object.values(item.price_ranges || {}).map(range => range.current_date).filter(Boolean).sort().at(-1);
      if (!finite(raw) || !finite(value) || (!value && finite(item.holding?.quantity) && item.holding.quantity !== 0)
          || day(mark) !== null && day(mark) > day(asOf)) { wholeScope = false; continue; }
      securities += value; gross += Math.abs(value); values.set(item, value);
      if (value && (day(mark) === null || item.stress_risk?.valuation_stale || day(asOf) - day(mark) > 7 * 86400000)) {
        addAssumption(day(mark) === null ? "undated_valuation" : "stale_valuation", item, mark ? {source_date:mark} : {});
      }
      if (!build(item, value)) { wholeScope = false; securities -= value; }
    }
    const cash = context.cashAccounts.filter(account => finite(account.value) && (account.value === 0 || upper(account.currency)));
    if (cash.length !== context.cashAccounts.length || context.cashBreakdownUnknown) wholeScope = false;
    const exposedCurrencies = new Set([...rows.flatMap(row => Object.keys(row.fx).filter(currency => row.fx[currency] > 0)),
      ...cash.filter(account => account.value !== 0).map(account => upper(account.currency))]);
    for (let index = rows.length - 1; index >= 0; index--) {
      const row = rows[index];
      if (row.directSovereign && row.countryRecovery && row.countryCurrency !== base && exposedCurrencies.has(row.countryCurrency)) {
        wholeScope = false; securities -= row.value; rows.splice(index, 1);
        addAssumption("recovery_model_required", row.item, {}, row.root);
      }
    }
    const netEquity = securities + sum(cash.map(account => account.value));
    const positiveCash = sum(cash.map(account => Math.max(0, account.value)));
    const knownGross = sum(rows.map(row => Math.abs(row.value))) + positiveCash;
    if (![netEquity, knownGross, gross].every(finite)) wholeScope = false;
    const foreign = [...new Set([...rows.flatMap(row => Object.keys(row.fx)), ...cash.map(account => upper(account.currency))].filter(currency => currency && currency !== base))];
    const paths = [{name:"fixed", fx:{}}];
    for (const sign of [-1, 1]) {
      paths.push({name:sign < 0 ? "all_foreign_down" : "all_foreign_up", fx:Object.fromEntries(foreign.map(currency => [currency, .15 * sign]))});
      for (const currency of foreign) paths.push({name:`${currency}_${sign < 0 ? "down" : "up"}`, fx:{[currency]:.15 * sign}});
    }
    const scenarios = [];
    const add = (name, local, fx) => {
      const pnl = sum(rows.map(row => {
        const localReturn = local(row);
        const currencyReturn = sum(Object.entries(row.fx).map(([currency, weight]) => weight * (fx[currency] || 0)));
        return row.value * ((1 + localReturn) * (1 + currencyReturn) - 1);
      }))
        + sum(cash.map(account => account.value * (fx[upper(account.currency)] || 0)));
      if (!finite(pnl)) { wholeScope = false; return; }
      scenarios.push({name, pnl, loss:Math.max(0, -pnl)});
    };
    for (const scenario of context.global) for (const path of paths) add(`${scenario.name}:${path.name}`, row => {
      if (row.moneyMarket) return ["recession", "inflation"].includes(scenario.name) ? -.01 : 0;
      if (row.equity) return row.sector ? ({recession:-.5, inflation:-.35, rally:.5, fx_only:0}[scenario.name]) : scenario.equity;
      const credit = row.widening * scenario.spread;
      return row.price(scenario.curve, credit < 0 ? Math.max(credit, -row.spread) : credit);
    }, path.fx);
    for (const issuer of new Set(rows.map(row => row.issuer).filter(Boolean))) {
      add(`issuer_distress:${issuer}`, row => row.issuer !== issuer ? 0 : row.equity ? -.6 : row.price(0, Math.max(.2 / row.duration, 2 * row.widening)), {});
      add(`issuer_rally:${issuer}`, row => row.issuer !== issuer ? 0 : row.equity ? 1 : row.price(-.02, -row.spread), {});
    }
    const countries = new Map();
    for (const row of rows) {
      const key = row.countryCode || "generic:" + row.countryCurrency;
      const old = countries.get(key);
      if (!old || row.country && (!old.rating || row.country.bucket > old.rating.bucket)) countries.set(key, {rating:row.country, currency:row.countryCurrency});
    }
    for (const [code, country] of countries) {
      const shock = country.rating ? context.countries[country.rating.bucket] : {equity:-.4, spread:.02, fx:-.15};
      add(`country_crisis:${code}`, row => {
        if ((row.countryCode || "generic:" + row.countryCurrency) !== code) return 0;
        if (row.moneyMarket) return -Math.max(.01, .25 * shock.spread);
        if (row.equity) return row.sector ? Math.min(-.5, shock.equity) : shock.equity;
        const spread = row.sovereign ? row.credit ? context.countries[row.credit.bucket].spread : shock.spread : Math.max(row.widening, row.sensitivity * shock.spread);
        return row.price(0, spread);
      }, country.currency && country.currency !== base ? {[country.currency]:shock.fx} : {});
    }
    const worst = scenarios.reduce((old, current) => old.loss >= current.loss ? old : current, {name:"none", loss:0});
    const debt = sum(cash.map(account => Math.max(0, -account.value)));
    const nonpositive = netEquity <= 0 && (knownGross > 0 || debt > 0);
    const point = !base || day(asOf) === null || !finite(netEquity) ? null : netEquity > 0 ? score(worst.loss / netEquity) : nonpositive ? 100 : knownGross === 0 && wholeScope ? 0 : null;
    const proxyGross = sum([...proxyRoots].map(item => Math.abs(values.get(item) || 0)));
    return {
      provisional_model:MODEL, provisional_basis:"asset_aware_scenarios", provisional_score:point,
      provisional_loss:nonpositive ? null : worst.loss,
      provisional_net_equity:finite(netEquity) && (knownGross || cash.some(account => account.value !== 0) || wholeScope) ? netEquity : null,
      provisional_proxy_gross:finite(proxyGross) ? proxyGross : null,
      provisional_assumptions:assumptions, provisional_scope:wholeScope ? "portfolio" : "known_values",
      ...(!wholeScope ? {provisional_range:{min:0, max:100}} : {}),
      provisional_worst_scenario:nonpositive ? "nonpositive_estimated_equity" : worst.name,
      provisional_scenarios:scenarios,
    };
  }
  return Object.freeze({MODEL, estimate});
});
