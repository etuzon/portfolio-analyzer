(function exposeTradePlanner(root, factory) {
  const planner = Object.freeze(factory());
  if (typeof module === "object" && module.exports) module.exports = planner;
  if (root) root.PortfolioTradePlanner = planner;
})(typeof globalThis === "object" ? globalThis : this, () => {
  "use strict";

  // Application heuristics, not a measured investor risk tolerance or broker
  // margin rules. Background: https://www.investor.gov/introduction-investing/investing-basics/asset-allocation
  const POLICY = Object.freeze({ reserve: 0.10, feeBuffer: 0.01, stockAccount: 0.10,
    stockPortfolio: 0.05, sectorAccount: 0.30, sectorPortfolio: 0.25,
    shortCollateral: 2, maxRisk: 75, maxRiskIncrease: 5, firstPositionRiskIncrease: 25, maxPriceAgeDays: 7 });
  const number = (value) => ["number", "string"].includes(typeof value) && String(value).trim() !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
  const upper = (value) => String(value || "").trim().toUpperCase();
  const total = (values) => values.reduce((sum, value) => sum + value, 0);
  const key = (value) => upper(value).replace(/[\s_.-]/g, "");
  const country = (value) => {
    const code = key(value);
    if (["USA", "US", "UNITEDSTATES", "UNITEDSTATESOFAMERICA", "ארצותהברית", 'ארה"ב', "ארה״ב"].includes(code)) return "US";
    if (["ISRAEL", "IL", "ISR", "ישראל"].includes(code)) return "IL";
    return "";
  };
  const listingCountry = (item) => {
    const listing = key(item.exchange || item.holding?.stock_market);
    if (["US", "USA", "NASDAQ", "NASDAQGS", "NASDAQGM", "NASDAQCM", "NMS", "NGM", "NCM", "NAS", "NYSE", "NYQ", "NYSEARCA", "ARCA", "AMEX", "NYSEAMERICAN", "OTC", "OTCMKTS", "PNK", "BATS", "CBOE"].includes(listing)) return "US";
    if (["TASE", "TLV", "TELAVIV"].includes(listing)) return "IL";
    return "";
  };
  function converter(quotes, baseCurrency) {
    const rates = {};
    for (const row of quotes || []) {
      const rate = number(row.quote?.rate);
      if (rate !== null && rate > 0) rates[upper(row.pair)] = rate;
    }
    const direct = (from, to) => from === to ? 1 : rates[`${from}/${to}`] || (rates[`${to}/${from}`] ? 1 / rates[`${to}/${from}`] : null);
    return (raw, from, to = baseCurrency) => {
      const amount = number(raw);
      from = upper(from); to = upper(to);
      if (amount === null || !from || !to) return null;
      if (amount === 0) return 0;
      let rate = direct(from, to);
      if (!rate) {
        const left = direct(from, baseCurrency), right = direct(baseCurrency, to);
        if (left && right) rate = left * right;
      }
      const converted = rate ? amount * rate : null;
      return converted !== null && Number.isFinite(converted) ? converted : null;
    };
  }
  function quote(item, now) {
    const ranges = item.price_ranges || {};
    for (const period of ["1m", "6m", "1y", "3y", "5y"]) {
      const range = ranges[period] || {};
      const price = number(range.current);
      const day = /^\d{4}-\d{2}-\d{2}$/.test(range.current_date || "") ? Date.parse(`${range.current_date}T00:00:00Z`) : NaN;
      const age = (now - day) / 86400000;
      if (price !== null && price > 0 && age >= 0 && age <= POLICY.maxPriceAgeDays) return { price, date: range.current_date };
    }
    return null;
  }
  function cashBalance(account, transactions, now) {
    let cash = number(account.initial_cash);
    if (cash === null) return null;
    for (const tx of transactions.filter((tx) => String(tx.account_db_id) === String(account.id))) {
      const sign = { BUY: -1, SELL: 1, SHORT: 1, DIVIDEND: 1, INTEREST: 1, FEE: -1 }[tx.action];
      if (!sign) continue;
      // Multi-currency ledger cash does not establish settled cash in a given
      // currency. Exclude it instead of treating FX estimates as buying power.
      if (upper(tx.currency) !== upper(account.currency)) return null;
      const quantity = number(tx.quantity), price = number(tx.price);
      if (quantity === null || price === null || quantity < 0 || price < 0) return null;
      const future = Date.parse(tx.trade_date) > now;
      if (future && sign > 0) continue;
      cash += sign * quantity * price;
    }
    return Number.isFinite(cash) ? cash : null;
  }
  function plan(context, request, adapters) {
    const now = Date.parse(context.calculated_at);
    const action = upper(request.action || "BUY");
    let requested = request.amount === "" || request.amount === null || request.amount === undefined ? null : number(request.amount);
    const blocked = (reason, excluded = []) => ({ status: "unavailable", reason, excluded, action, requested, policy: POLICY });
    if (!["BUY", "SHORT"].includes(action) || (request.amount !== "" && request.amount != null && (requested === null || requested <= 0))) return blocked("invalid_request");
    const security = context.security;
    if (!security) return blocked(context.reason || "listing_unverified");
    const h = security.holding || {};
    if (!["EQUITY", "ETF"].includes(upper(h.asset_class)) || adapters.derivative(security)) return blocked("unsupported_instrument");
    const listing = listingCountry(security);
    if (!listing) return blocked("listing_unverified");
    const current = quote(security, now);
    if (!current) return blocked("price_unavailable");
    const base = upper(context.base_currency), currency = upper(h.currency);
    const convert = converter(context.fx_quotes, base);
    if (requested !== null && request.amountCurrency) {
      requested = convert(requested, request.amountCurrency, currency);
      if (requested === null) return blocked("fx_unavailable");
    }
    const unitBase = convert(current.price, currency);
    if (unitBase === null || unitBase <= 0) return blocked("fx_unavailable");
    const accounts = context.accounts.filter((account) => ["INVESTMENT", "BANK"].includes(upper(account.type)));
    const accountIds = new Set(accounts.map((account) => String(account.id)));
    const snapshotRows = context.items.filter((item) => accountIds.has(String(item.holding?.account_id)));
    const value = (item) => convert(item.holding.market_value, item.holding.currency);
    if (snapshotRows.some((item) => {
      const quantity = number(item.holding.quantity), amount = number(item.holding.market_value), currentQuote = quote(item, now);
      if (quantity === null || amount === null || value(item) === null || Math.sign(quantity) !== Math.sign(amount)) return true;
      if (quantity === 0) return false;
      if (!currentQuote) return true;
      return false;
    })) return blocked("valuation_unavailable");
    // Local ledger snapshots can retain the entry valuation while analytics
    // carry a newer quote. Reprice only this immutable planning snapshot.
    const rows = snapshotRows.map((item) => ({ ...item, holding: { ...item.holding,
      market_value: Number(item.holding.quantity) === 0 ? 0 : Number(item.holding.quantity) * quote(item, now).price } }));
    const cashByAccount = new Map(accounts.map((account) => [String(account.id), cashBalance(account, context.transactions, now)]));
    const cashValues = accounts.map((account) => convert(cashByAccount.get(String(account.id)), account.currency));
    // Unknown balances cannot be silently removed from a portfolio denominator.
    if (cashValues.some((cash) => cash === null)) return blocked("cash_unverified");
    const nav = total(rows.map(value)) + total(cashValues);
    if (!Number.isFinite(nav) || nav <= 0) return blocked("no_cash");
    const symbol = upper(h.symbol);
    const sameSymbol = (item) => upper(item.holding.symbol) === symbol;
    const sector = upper(h.sector || adapters.industry(security));
    const sameSector = (item) => upper(item.holding.sector || adapters.industry(item)) === sector;
    const exposure = (items, predicate) => total(items.filter(predicate).map((item) => Math.abs(value(item))));
    const portfolioStock = exposure(rows, sameSymbol), portfolioSector = sector ? exposure(rows, sameSector) : 0;
    const exclusions = [], candidates = [];
    for (const account of context.accounts) {
      const reject = (reason) => exclusions.push({ account, reason });
      if (upper(account.type) !== "INVESTMENT") { reject("account_type"); continue; }
      if (country(account.location) !== listing) { reject("account_country"); continue; }
      if (upper(account.currency) !== currency) { reject("account_currency"); continue; }
      const positions = rows.filter((item) => String(item.holding.account_id) === String(account.id));
      if (positions.some((item) => adapters.derivative(item) || Number(item.holding.quantity) < 0)) { reject("collateral_unverified"); continue; }
      if (action === "SHORT" && positions.some((item) => sameSymbol(item) && Number(item.holding.quantity) > 0)) { reject("existing_long"); continue; }
      const cash = cashByAccount.get(String(account.id));
      if (!(cash > 0)) { reject("no_cash"); continue; }
      const cashBase = convert(cash, currency);
      const accountNav = total(positions.map(value)) + cashBase;
      const horizon = adapters.horizon(account);
      const before = adapters.risk(positions, { cash: cashBase, cashCurrency: currency, horizonYears: horizon,
        baseCurrency: base, normalizeField: (item, field) => convert(item.holding[field], item.holding.currency) });
      if (!Number.isFinite(before.score) || before.score >= POLICY.maxRisk) { reject("risk_limit"); continue; }
      let scale = before.score >= 60 ? 0.5 : before.score >= 40 ? 0.75 : 1;
      if (horizon === null || horizon < 7) scale *= 0.5;
      if (horizon !== null && horizon < 3) scale *= 0.5;
      if (!sector) scale *= 0.5;
      if (adapters.volatility(security) > 60) scale *= 0.5;
      if (action === "SHORT") scale *= 0.5;
      const reserveFraction = (horizon !== null && horizon < 7) || before.score >= 60 || action === "SHORT" ? 0.20 : POLICY.reserve;
      const reserve = Math.max(accountNav * reserveFraction, cashBase * 0.20);
      const collateral = action === "SHORT" ? POLICY.shortCollateral : 1;
      const positionLimit = action === "SHORT" ? 0.025 : POLICY.stockAccount;
      const portfolioLimit = action === "SHORT" ? 0.02 : POLICY.stockPortfolio;
      const limits = [
        { reason: "cash_reserve", value: (cashBase - reserve) / (collateral + POLICY.feeBuffer) },
        { reason: "stock_account_limit", value: accountNav * positionLimit - exposure(positions, sameSymbol) },
        { reason: "stock_portfolio_limit", value: nav * portfolioLimit - portfolioStock },
        { reason: "risk_sizing", value: Math.min(accountNav * 0.05, nav * 0.02, cashBase * 0.25) * scale },
      ];
      if (sector) limits.push(
        { reason: "sector_account_limit", value: accountNav * POLICY.sectorAccount - exposure(positions, sameSector) },
        { reason: "sector_portfolio_limit", value: nav * POLICY.sectorPortfolio - portfolioSector });
      if (requested !== null) limits.push({ reason: "requested_amount", value: convert(requested, currency) });
      limits.sort((a, b) => a.value - b.value);
      let quantity = Math.floor(Math.max(0, limits[0].value) / unitBase);
      // The existing risk model adds industry/issuer/volatility components on the first
      // holding even for a tiny starter position. Allow that discontinuity
      // without changing the portfolio's shared risk formula.
      const riskIncreaseLimit = positions.length ? POLICY.maxRiskIncrease : POLICY.firstPositionRiskIncrease;
      let after, projected, costBase, riskReduced = false;
      while (quantity > 0) {
        const notional = quantity * current.price;
        costBase = quantity * unitBase;
        const existing = positions.find(sameSymbol);
        projected = positions.map((item) => item === existing ? { ...item, holding: { ...item.holding,
          market_value: Number(item.holding.market_value) + (action === "SHORT" ? -notional : notional),
          quantity: Number(item.holding.quantity) + (action === "SHORT" ? -quantity : quantity) } } : item);
        if (!existing) projected.push({ ...security, holding: { ...h, account_id: account.id,
          quantity: action === "SHORT" ? -quantity : quantity, market_value: action === "SHORT" ? -notional : notional } });
        after = adapters.risk(projected, { cash: Math.max(0, cashBase - costBase * (collateral + POLICY.feeBuffer)),
          cashCurrency: currency, horizonYears: horizon, baseCurrency: base,
          normalizeField: (item, field) => convert(item.holding[field], item.holding.currency) });
        if (Number.isFinite(after.score) && after.score <= Math.min(POLICY.maxRisk, before.score + riskIncreaseLimit)) break;
        riskReduced = true;
        quantity = Math.floor(quantity / 2);
      }
      if (!quantity) { reject(limits[0].value < unitBase ? limits[0].reason : "risk_limit"); continue; }
      const amount = quantity * current.price;
      const cashUsed = amount * (collateral + POLICY.feeBuffer);
      const stockBefore = exposure(positions, sameSymbol);
      const score = after.score + Math.max(0, after.score - before.score) * 2
        + (stockBefore + costBase) / accountNav * 100 + (sector ? exposure(positions, sameSector) / accountNav * 10 : 5)
        + (requested !== null ? (requested - amount) / requested * 25 : 0);
      candidates.push({ account, amount, quantity, currency, cash, reserve: convert(reserve, base, currency),
        cashRemaining: cash - cashUsed, collateral: action === "SHORT" ? amount * collateral : null,
        feeAllowance: amount * POLICY.feeBuffer, riskBefore: before.score, riskAfter: after.score,
        weightBefore: stockBefore / accountNav * 100, weightAfter: (stockBefore + costBase) / accountNav * 100,
        limit: riskReduced ? "risk_limit" : limits[0].reason, horizon, riskIncreaseLimit, unknownSector: !sector, score });
    }
    candidates.sort((a, b) => a.score - b.score || b.amount - a.amount || String(a.account.id).localeCompare(String(b.account.id)));
    return { status: candidates.length ? "ok" : "unavailable", reason: candidates.length ? null : "no_suitable_account",
      recommendation: candidates[0] || null, alternatives: candidates.slice(1), excluded: exclusions,
      action, requested, policy: POLICY, symbol, quote: current, calculatedAt: context.calculated_at,
      refreshPending: context.refresh_pending };
  }
  return { plan, converter, quote, cashBalance, listingCountry, POLICY };
});
