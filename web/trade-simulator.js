(function exposeTradeSimulator(root, factory) {
  const simulator = Object.freeze(factory());
  if (typeof module === "object" && module.exports) module.exports = simulator;
  if (root) root.PortfolioTradeSimulator = simulator;
})(typeof globalThis === "object" ? globalThis : this, () => {
  "use strict";
  const num = (value) => ["string", "number"].includes(typeof value) && String(value).trim() !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
  const upper = (value) => String(value || "").trim().toUpperCase();
  const market = (value) => {
    const key = upper(value).replace(/[\s_-]/g, "");
    return ({ NASDAQGS: "NASDAQ", NASDAQGM: "NASDAQ", NASDAQCM: "NASDAQ", NAS: "NASDAQ", NMS: "NASDAQ",
      NYSEAMERICAN: "AMEX", NYSEMKT: "AMEX", ARCA: "NYSEARCA", OTCMKTS: "OTC", TLV: "TASE", TELAVIV: "TASE" }[key] || key);
  };
  const sum = (rows) => rows.reduce((a, b) => a + b, 0);
  const listing = (item) => market(item.holding.stock_market || item.exchange);
  const identity = (item) => [upper(item.holding.symbol), listing(item), upper(item.holding.currency), upper(item.holding.asset_class)].join("|");

  function priceDivisor(item) {
    const location = upper(item.holding.location), bond = ["BOND", "BONDS"].includes(upper(item.holding.asset_class));
    if (["ISRAEL", "IL", "STATE OF ISRAEL", "ISR", "ישראל"].includes(location)) return 100;
    if (["USA", "US", "U.S.", "U.S.A.", "UNITED STATES", "UNITED STATES OF AMERICA"].includes(location)) return bond ? 100 : 1;
    if (listing(item) === "TASE" || market(item.exchange) === "TASE") return 100;
    const usMarkets = ["US", "USA", "NASDAQ", "NYSE", "AMEX", "NYSEARCA", "OTC", "BATS", "CBOE"];
    return bond && (usMarkets.includes(listing(item)) || usMarkets.includes(market(item.exchange))) ? 100 : 1;
  }

  function simulate(context, trades, adapters) {
    context = JSON.parse(JSON.stringify(context));
    const planner = typeof module === "object" && module.exports ? require("./trade-planner.js") : globalThis.PortfolioTradePlanner;
    const now = Date.parse(context.calculated_at), base = upper(context.base_currency);
    const convert = planner.converter(context.fx_quotes, base);
    const errors = [], warnings = [], executed = [];
    const fail = (rowId, reason) => errors.push({ rowId, reason });
    const invalid = () => ({ status: "invalid", errors, warnings, accounts: [], total: null, trades: [] });
    if (!Number.isFinite(now) || !base || !Array.isArray(trades) || !trades.length || trades.length > 100) {
      fail(null, "invalid_request"); return invalid();
    }
    const datedQuote = (item, accountId) => {
      const current = planner.quote(item, now);
      if (current && (now - Date.parse(current.date + "T00:00:00Z")) / 86400000 > planner.POLICY.maxPriceAgeDays) {
        if (!warnings.some((w) => w.symbol === item.holding.symbol && w.accountId === accountId && w.date === current.date)) {
          warnings.push({ reason: "price_stale", symbol: item.holding.symbol, accountId, date: current.date });
        }
      }
      return current;
    };
    // Cash is a ledger estimate, not confirmed broker buying power. Future
    // transactions have no effect on this as-of snapshot.
    const ledgerCash = (account) => {
      let cash = num(account.initial_cash);
      if (cash === null) return null;
      for (const tx of context.transactions || []) {
        if (String(tx.account_db_id) !== String(account.id)) continue;
        const sign = { BUY: -1, SELL: 1, SHORT: 1, DIVIDEND: 1, INTEREST: 1, FEE: -1 }[upper(tx.action)];
        if (!sign) continue;
        const day = Date.parse(tx.trade_date);
        if (!Number.isFinite(day)) return null;
        if (day > now) continue;
        const quantity = num(tx.quantity), price = num(tx.price);
        if (upper(tx.currency) !== upper(account.currency) || quantity === null || price === null || quantity < 0 || price < 0) return null;
        cash += sign * quantity * price;
      }
      return Number.isFinite(cash) ? cash : null;
    };
    const accountTypes = new Map((context.accounts || []).map((account) => [String(account.id), upper(account.type)]));
    const books = new Map((context.accounts || []).filter((account) => upper(account.type) === "INVESTMENT").map((account) => [String(account.id), {
      account, cash: ledgerCash(account), positions: [], issue: null,
    }]));
    // The dashboard's position snapshot includes every ledger date. It cannot
    // establish today's quantity when a future security trade exists (even a
    // future full sale can remove the row). Do not invent an as-of position.
    for (const tx of context.transactions || []) {
      if (["ADD", "REMOVE", "BUY", "SELL", "SHORT"].includes(upper(tx.action)) && Date.parse(tx.trade_date) > now) {
        const book = books.get(String(tx.account_db_id));
        if (book) book.issue = "future_transactions";
      }
    }
    let totalIssue = null;
    for (const item of context.items || []) {
      const h = item.holding || {}, book = books.get(String(h.account_id));
      if (!book) {
        if (accountTypes.has(String(h.account_id)) || ["BANK", "LONG-TERM SAVINGS", "ESOP"].includes(upper(h.account_type))) continue;
        totalIssue = "unknown_account"; continue;
      }
      const quantity = num(h.quantity);
      if (quantity === 0) continue;
      const quote = datedQuote(item, String(book.account.id));
      if (quantity === null) book.issue = "valuation_unavailable";
      const key = identity(item), prior = book.positions.find((p) => identity(p) === key);
      if (prior && prior._price !== (quote?.price ?? null)) book.issue = "valuation_unavailable";
      if (prior) prior.holding.quantity += quantity || 0;
      else book.positions.push({ ...item, holding: { ...h, quantity: quantity || 0 }, _price: quote?.price ?? null });
    }
    const cloneBooks = () => new Map([...books].map(([id, book]) => [id, { ...book,
      positions: book.positions.map((p) => ({ ...p, holding: { ...p.holding } })) }]));
    const projected = cloneBooks();
    for (const trade of trades) {
      const id = trade.id, book = projected.get(String(trade.accountId));
      if (!book || upper(book.account.type) !== "INVESTMENT") { fail(id, "account_type"); continue; }
      if (book.issue === "future_transactions") { fail(id, "future_transactions"); continue; }
      const entry = (context.securities || []).find((s) => upper(s.symbol) === upper(trade.symbol) && market(s.stock_market) === market(trade.market));
      const security = entry?.security;
      if (!security) { fail(id, entry?.reason || "listing_unverified"); continue; }
      const h = security.holding, currency = upper(h.currency), quantity = num(trade.quantity);
      if (adapters.derivative(security)) {
        fail(id, "unsupported_instrument"); continue;
      }
      if (!["EQUITY", "RSU", "ETF", "BOND", "BONDS", "MUTUALFUND"].includes(upper(h.asset_class))) {
        fail(id, "unsupported_asset_class"); continue;
      }
      if (currency !== upper(book.account.currency)) { fail(id, "account_currency"); continue; }
      const current = datedQuote(security, String(book.account.id));
      const entered = trade.priceInput !== "" && trade.priceInput != null;
      const input = entered ? num(trade.priceInput) : current ? current.price * priceDivisor(security) : null;
      const price = input === null ? null : input / priceDivisor(security);
      const fee = trade.fee === "" || trade.fee == null ? 0 : num(trade.fee);
      const action = upper(trade.action);
      if (!["BUY", "SELL", "SHORT"].includes(action) || quantity === null || quantity <= 0 || fee === null || fee < 0 || (entered && (price === null || price <= 0))) {
        fail(id, "invalid_trade"); continue;
      }
      if (price === null || price <= 0) { fail(id, "price_unavailable"); continue; }
      const same = (item) => identity(item) === identity(security);
      let position = book.positions.find(same);
      const held = position?.holding.quantity || 0;
      if (action === "SELL" && (held <= 0 || quantity > held + 1e-9)) { fail(id, "sell_exceeds_holding"); continue; }
      if (action === "SHORT" && held > 1e-9) { fail(id, "existing_long"); continue; }
      const delta = action === "BUY" ? quantity : -quantity;
      const quantityAfter = Math.abs(held + delta) < 1e-9 ? 0 : held + delta;
      const notional = quantity * price, cashImpact = (action === "BUY" ? -notional : notional) - fee;
      if (![quantityAfter, notional, cashImpact].every(Number.isFinite)) { fail(id, "invalid_trade"); continue; }
      if (!position) {
        position = { ...security, holding: { ...h, account_id: book.account.id, quantity: 0 }, _price: current?.price ?? null };
        book.positions.push(position);
      }
      position.holding.quantity = quantityAfter;
      if (book.cash !== null) book.cash += cashImpact;
      if (book.cash !== null && !Number.isFinite(book.cash)) { fail(id, "invalid_trade"); continue; }
      executed.push({ ...trade, action, price, priceInput: input, priceDate: entered ? null : current.date,
        currency, notional, cashImpact, quantityAfter });
    }
    if (errors.length) return invalid();

    const snapshot = (book) => {
      const positions = book.positions.filter((p) => p.holding.quantity !== 0).map((p) => ({ ...p,
        holding: { ...p.holding, market_value: p._price === null ? null : p.holding.quantity * p._price } }));
      const currency = upper(book.account.currency);
      const localValues = positions.map((p) => convert(p.holding.market_value, p.holding.currency, currency));
      const baseValues = positions.map((p) => convert(p.holding.market_value, p.holding.currency));
      const cashBase = convert(book.cash, currency);
      const missingValuation = positions.some((p) => p._price === null || !p.holding.currency || !p.holding.asset_class);
      let reason = book.issue || (missingValuation ? "valuation_unavailable" : null) || (book.cash === null ? "cash_unverified" : null);
      if (localValues.some((v) => v === null) || baseValues.some((v) => v === null) || (book.cash !== null && cashBase === null)) reason ||= "fx_unavailable";
      const valued = !book.issue && !missingValuation && localValues.every((v) => v !== null);
      const netValue = valued && book.cash !== null ? sum(localValues) + book.cash : null;
      const grossExposure = valued ? sum(localValues.map(Math.abs)) : null;
      const shortExposure = valued ? Math.max(0, -sum(localValues.filter((v) => v < 0))) : null;
      const hasLiability = positions.some((p) => p.holding.quantity < 0 || adapters.derivative(p));
      const risk = !reason ? adapters.risk(positions, { cash: cashBase, cashCurrency: currency,
        horizonYears: adapters.horizon(book.account), baseCurrency: base,
        normalizeField: (item, field) => convert(item.holding[field], item.holding.currency) }) : null;
      const availableCash = book.cash !== null && !hasLiability ? book.cash : null;
      const valueReason = book.issue || (missingValuation ? "valuation_unavailable" : null)
        || (localValues.some((v) => v === null) ? "fx_unavailable" : null);
      const cashReason = book.cash === null ? "cash_unverified" : null;
      const issues = positions.flatMap((p) => {
        const reasons = [];
        if (p._price === null) reasons.push("price_missing");
        if (!p.holding.currency) reasons.push("holding_currency_missing");
        if (!p.holding.asset_class) reasons.push("holding_class_missing");
        if (!reasons.length && convert(p.holding.market_value, p.holding.currency) === null) reasons.push("fx_unavailable");
        return reasons.map((reason) => ({ symbol: p.holding.symbol, reason }));
      });
      return { cash: book.cash, netValue, grossExposure, shortExposure, availableCash, risk, reason, issues,
        cashDeficit: book.cash !== null ? Math.max(0, -book.cash) : null,
        unavailableReasons: { cash: cashReason, netValue: netValue === null ? valueReason || cashReason : null,
          grossExposure: grossExposure === null ? valueReason : null, shortExposure: shortExposure === null ? valueReason : null,
          availableCash: availableCash === null ? cashReason || "collateral_unverified" : null, risk: risk === null ? reason : null },
        _positions: positions, _cashBase: cashBase,
        _riskWeight: !reason ? sum(baseValues.map(Math.abs)) + Math.max(0, cashBase) : null };
    };
    const accounts = [...books].map(([id, book]) => ({ account: book.account,
      before: snapshot(book), after: snapshot(projected.get(id)) }));
    const combined = (phase) => {
      const rows = accounts.map((a) => a[phase]);
      const field = (name) => {
        const values = accounts.map((a) => convert(a[phase][name], a.account.currency));
        return totalIssue || values.some((v) => v === null) ? null : sum(values);
      };
      const cash = field("cash"), netValue = field("netValue"), grossExposure = field("grossExposure"), shortExposure = field("shortExposure");
      const reason = totalIssue || rows.find((r) => r.reason)?.reason || null;
      let risk = null;
      if (!reason && rows.length) {
        const horizons = accounts.map((a) => adapters.horizon(a.account)).filter((v) => v != null);
        const combinedRisk = adapters.risk(rows.flatMap((r) => r._positions), { cash, baseCurrency: base,
          cashDebt: sum(rows.map((r) => Math.max(0, -r._cashBase))),
          horizonYears: horizons.length ? Math.min(...horizons) : null,
          normalizeField: (item, name) => convert(item.holding[name], item.holding.currency) });
        const denominator = sum(rows.map((r) => r._riskWeight));
        const weighted = denominator ? sum(rows.map((r) => r.risk.score * r._riskWeight)) / denominator : 0;
        const insolvent = combinedRisk.net_equity <= 0 && (grossExposure > 0 || combinedRisk.cash_debt > 0);
        risk = { ...combinedRisk, score: insolvent ? 100 : Math.min(100, Math.max(0, Math.round(0.75 * combinedRisk.score + 0.25 * weighted))) };
      }
      const availableCash = field("availableCash");
      const unavailableReasons = {};
      for (const [name, value] of Object.entries({ cash, netValue, grossExposure, shortExposure, availableCash, risk })) {
        unavailableReasons[name] = value === null ? totalIssue || rows.find((r) => r[name] === null)?.unavailableReasons[name] || reason : null;
      }
      const blockedAccounts = accounts.filter((entry) => entry[phase].risk === null).map((entry) => ({
        accountId: entry.account.id, reason: entry[phase].reason, currency: entry.account.currency,
        cashDeficit: entry[phase].cashDeficit,
      }));
      return { cash, netValue, grossExposure, shortExposure, availableCash, risk, reason, unavailableReasons, blockedAccounts,
        cashDeficit: field("cashDeficit") };
    };
    const total = { before: combined("before"), after: combined("after") };
    for (const entry of accounts) for (const phase of ["before", "after"]) {
      delete entry[phase]._positions; delete entry[phase]._cashBase; delete entry[phase]._riskWeight;
    }
    return { status: "ok", accounts, total, trades: executed, warnings, errors,
      baseCurrency: base, calculatedAt: context.calculated_at, refreshPending: context.refresh_pending };
  }
  return { simulate, priceDivisor };
});
