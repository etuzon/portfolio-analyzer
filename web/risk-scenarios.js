/* Independent, read-only sale alternatives using the injected dashboard model. */
(function (root, factory) {
  const api = factory(typeof module === "object" && module.exports ? require("./trade-planner.js") : root.PortfolioTradePlanner);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PortfolioRiskScenarios = api;
})(typeof globalThis === "object" ? globalThis : this, function (planner) {
  "use strict";
  const clone = value => JSON.parse(JSON.stringify(value));
  const upper = value => String(value || "").trim().toUpperCase();
  const number = value => typeof value === "number" && Number.isFinite(value) ? value : null;
  const fail = code => { throw new Error(code); };
  const sign = { BUY:-1, SELL:1, SHORT:1, DIVIDEND:1, INTEREST:1, FEE:-1, CASH_IN:1, CASH_OUT:-1 };
  const securityActions = new Set(["ADD", "REMOVE", "BUY", "SELL", "SHORT"]);
  function rateToBase(context, currency) {
    if (currency === context.base_currency) return 1;
    const rates = Object.fromEntries((context.fx?.quotes || []).map(row => [row.pair, number(row.quote?.rate)]));
    const direct = rates[`${currency}/${context.base_currency}`], inverse = rates[`${context.base_currency}/${currency}`];
    return direct > 0 ? direct : inverse > 0 ? 1 / inverse : null;
  }
  function cashFor(context, account) {
    let cash = number(account.initial_cash);
    if (cash === null || !/^[A-Z]{3}$/.test(account.currency || "")) fail("cash_unavailable");
    const now = Date.parse(context.observed_at), cutoff = planner.ledgerCutoff(now);
    for (const tx of context.transactions || []) {
      if (String(tx.account_db_id) !== String(account.id)) continue;
      const action = upper(tx.action);
      if (!(action in sign) && !securityActions.has(action)) continue;
      const day = Date.parse(`${tx.trade_date}T00:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(tx.trade_date || "") || !Number.isFinite(day)
          || new Date(day).toISOString().slice(0, 10) !== tx.trade_date) fail("cash_unavailable");
      if (day > cutoff) fail("future_transactions");
      if (!(action in sign)) continue;
      const quantity = number(tx.quantity), price = number(tx.price);
      if (quantity === null || price === null || quantity < 0 || price < 0) fail("cash_unavailable");
      const impact = sign[action] * quantity * price;
      if (!Number.isFinite(impact) || (impact && upper(tx.currency) !== account.currency)) fail("cash_unavailable");
      cash += impact;
    }
    if (!Number.isFinite(cash)) fail("cash_unavailable");
    return cash;
  }
  function validate(context) {
    if (context?.model !== "portfolio-risk-v2" || !Array.isArray(context.items) || !Array.isArray(context.accounts)
        || !Number.isFinite(Date.parse(context.observed_at)) || !/^[A-Z]{3}$/.test(context.base_currency || "")) fail("context_unavailable");
    const accounts = new Map(context.accounts.map(row => [String(row.id), row]));
    for (const account of context.accounts) {
      // Endpoint context is already canonical; reject an accidental scope leak.
      if (upper(account.type) === "ESOP") fail("context_unavailable");
      const cash = cashFor(context, account);
      if (cash !== 0 && !rateToBase(context, account.currency)) fail("missing_fx");
    }
    for (const item of context.items) {
      const h = item.holding || {};
      if (!accounts.has(String(h.account_id)) || !h.asset_class || !h.currency
          || ["RSU", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(upper(h.asset_class))) fail("context_unavailable");
      if (number(h.quantity) === null || number(h.market_value) === null
          || (h.quantity !== 0 && h.market_value === 0)) fail("valuation_unavailable");
      if (h.market_value !== 0 && !rateToBase(context, h.currency)) fail("missing_fx");
    }
  }
  function candidate(context, index, options) {
    const item = context.items[index], h = item.holding;
    const account = context.accounts.find(row => String(row.id) === String(h.account_id));
    if (upper(account.type) !== "INVESTMENT" || (options.accountId && String(account.id) !== String(options.accountId))) return null;
    if (h.quantity <= 0 || h.market_value <= 0) fail("long_positions_only");
    const derivative = options.derivative ? options.derivative(item) : ["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(upper(h.asset_sub_class)) || /(?:2X|3X|LEVERAGED)/.test(upper(h.symbol));
    if (derivative || !["EQUITY", "ETF", "BOND", "BONDS", "MUTUALFUND"].includes(upper(h.asset_class))) fail("unsupported_instrument");
    const quote = planner.quote(item, Date.parse(context.observed_at));
    if (!quote) fail("price_unavailable");
    if (Math.abs(h.quantity * quote.price - h.market_value) > Math.max(1e-6, Math.abs(h.market_value) * 1e-6)) fail("valuation_mismatch");
    const converted = h.currency !== account.currency;
    if (converted && !options.convertProceeds) fail("conversion_required");
    const holdingRate = rateToBase(context, h.currency), accountRate = rateToBase(context, account.currency);
    if (!holdingRate || !accountRate) fail("missing_fx");
    return { id:String(index), index, accountId:String(account.id), accountLabel:account.account_id || String(account.id),
      symbol:h.symbol, label:item.label || h.symbol, currency:h.currency, accountCurrency:account.currency,
      heldQuantity:h.quantity, unitPrice:quote.price, maxAmount:h.quantity * quote.price, quoteDate:quote.date,
      stale:(Date.parse(context.observed_at) - Date.parse(`${quote.date}T00:00:00Z`)) / 86400000 > planner.POLICY.maxPriceAgeDays,
      converted, conversionRate:holdingRate / accountRate, cashBefore:cashFor(context, account) };
  }
  function accountRisk(snapshot, id) {
    const risk = snapshot.accounts.find(row => String(row.key) === String(id))?.risk;
    // An empty zero-cash account is absent from the existing dashboard rollup.
    return risk || { score:0, components:{}, cash_debt:0, net_equity:0 };
  }
  function checkedSnapshot(calculate, context) {
    // Freeze derived ages on the capture day, rather than the live slider clock.
    const captured = new Date(context.observed_at);
    for (const account of context.accounts) for (const person of account.persons || []) {
      if (Number(person.age)) continue;
      const birth = new Date(`${person.birth_date}T00:00:00`);
      if (!Number.isFinite(birth.getTime())) continue;
      const days = (Date.UTC(captured.getFullYear(), captured.getMonth(), captured.getDate())
        - Date.UTC(birth.getFullYear(), birth.getMonth(), birth.getDate())) / 86400000;
      if (days >= 0) person.age = Math.round(days / 365.2425 * 100) / 100;
    }
    const result = calculate(context);
    if (!result?.total || !Number.isFinite(result.total.score) || !Array.isArray(result.accounts)
        || result.accounts.some(row => !Number.isFinite(row.risk?.score))) fail("context_unavailable");
    return result;
  }
  function project(context, source, amount, options) {
    if (typeof amount === "string" && amount.trim() !== "") amount = Number(amount);
    if (number(amount) === null || amount < 0) fail("invalid_amount");
    if (amount > source.maxAmount) fail("amount_exceeds_holding");
    if (typeof options?.calculate !== "function") fail("context_unavailable");
    const row = candidate(context, source.index, options);
    if (!row || row.id !== source.id) fail("context_unavailable");
    const baseline = options.baseline || checkedSnapshot(options.calculate, clone(context));
    const projected = clone(context);
    const item = projected.items[row.index];
    const quantity = amount === row.maxAmount ? row.heldQuantity : amount / row.unitPrice;
    const remaining = row.heldQuantity - quantity;
    if (remaining === 0) projected.items.splice(row.index, 1);
    else {
      item.holding.quantity = remaining;
      item.holding.market_value = remaining * row.unitPrice;
    }
    const proceedsAccount = amount * row.conversionRate;
    const account = projected.accounts.find(entry => String(entry.id) === row.accountId);
    account.initial_cash += proceedsAccount;
    if (!Number.isFinite(account.initial_cash) || !Number.isFinite(proceedsAccount)) fail("invalid_amount");
    // Preserve the exact original values for the no-op, including quote-rounding differences.
    const after = amount === 0 ? baseline : checkedSnapshot(options.calculate, projected);
    const accountBefore = accountRisk(baseline, row.accountId), accountAfter = accountRisk(after, row.accountId);
    const totalBefore = baseline.total, totalAfter = after.total;
    const improves = accountAfter.score <= accountBefore.score && totalAfter.score <= totalBefore.score
      && (accountAfter.score < accountBefore.score || totalAfter.score < totalBefore.score);
    const reasons = Object.keys(accountBefore.components || {}).filter(key => key !== "data_quality")
      .map(key => [key, (accountBefore.components[key] || 0) - (accountAfter.components?.[key] || 0)])
      .filter(([, delta]) => delta > .01).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([key]) => key);
    return { ...row, amount, quantity, proceedsAccount, cashAfter:row.cashBefore + proceedsAccount,
      accountBefore, accountAfter, totalBefore, totalAfter, reasons, improves };
  }
  async function generate(context, options) {
    validate(context);
    if (typeof options?.calculate !== "function") fail("context_unavailable");
    const maximum = options.maxScenarios ?? 5;
    if (!Number.isInteger(maximum) || maximum < 1 || maximum > 20) fail("invalid_maximum");
    const baseline = checkedSnapshot(options.calculate, clone(context));
    const config = { ...options, baseline }, scenarios = [], excluded = [];
    const seen = new Set();
    for (let index = 0; index < context.items.length; index++) {
      if (options.cancelled?.()) fail("superseded");
      if (index % 8 === 0) await new Promise(resolve => setTimeout(resolve, 0));
      const h = context.items[index].holding;
      try {
        const row = candidate(context, index, config);
        if (!row) continue;
        const key = [row.accountId, upper(row.symbol), upper(h.stock_market), row.currency, upper(h.asset_class)].join("|");
        if (seen.has(key)) continue;
        seen.add(key);
        const choices = [.1, .25, .5].map(fraction => project(context, row, row.maxAmount * fraction, config)).filter(choice => choice.improves);
        choices.sort((a, b) => (a.totalAfter.score - b.totalAfter.score) || (a.accountAfter.score - b.accountAfter.score) || (a.amount - b.amount));
        if (choices.length) scenarios.push(choices[0]);
      } catch (error) { excluded.push({ symbol:h.symbol, accountId:String(h.account_id), code:error.message }); }
    }
    scenarios.sort((a, b) => ((b.totalBefore.score - b.totalAfter.score) - (a.totalBefore.score - a.totalAfter.score))
      || ((b.accountBefore.score - b.accountAfter.score) - (a.accountBefore.score - a.accountAfter.score)) || String(a.symbol).localeCompare(String(b.symbol)));
    return { baseline, scenarios:scenarios.slice(0, maximum), excluded, eligibleCount:scenarios.length, observed_at:context.observed_at };
  }
  return Object.freeze({ generate, project, rateToBase });
});
