/* Stable, non-mutating ordering of the currently displayed holdings only. */
(function (root) {
  "use strict";
  const monetary = new Set(["value", "profit", "high", "low", "support", "resistance", "ma"]);
  const text = new Set(["security", "account", "status"]);
  const finite = (value) => typeof value === "number" && Number.isFinite(value) ? value : null;
  function valueFor(item, key, context) {
    const h = item.holding || {};
    const range = item.price_ranges?.["1y"] || {};
    const levels = item.support_resistance?.["1y"] || {};
    const average = item.moving_averages?.[context.maPeriod || "30"] || {};
    const trend = key === "income" ? item.profit_trend : item.dividend_trend;
    let value;
    switch (key) {
      case "security": return String(h.symbol || "").trim() || null;
      case "account": return context.account(h) || null;
      case "status": return context.status(item) || null;
      case "risk": return finite(context.risk(item));
      case "value": value = h.market_value; break;
      case "profit": value = h.unrealized_profit; break;
      case "high": value = ["ok", "partial"].includes(range.state) ? range.high : null; break;
      case "low": value = ["ok", "partial"].includes(range.state) ? range.min : null; break;
      case "support": value = levels.state === "ok" ? levels.support?.price : null; break;
      case "resistance": value = levels.state === "ok" ? levels.resistance?.price : null; break;
      case "ma": value = levels.state === "ok" && average.state === "ok" ? average.value : null; break;
      case "income":
      case "dividend": return trend && !["missing", "pending", "error"].includes(trend.state) ? finite(trend.percent_change) : null;
      default: return null;
    }
    return finite(value) === null ? null : finite(context.amount(value, h.currency));
  }
  function sortRows(rows, selection, context) {
    if (!selection?.key) return [...rows];
    const collator = new Intl.Collator(context.language === "he" ? "he" : "en", {numeric: true, sensitivity: "base"});
    const direction = selection.direction === "asc" ? 1 : -1;
    return rows.map((item, index) => ({item, index, value: valueFor(item, selection.key, context)}))
      .sort((a, b) => {
        // Missing inputs stay last in either direction; equal values retain
        // source order, including separate accounts holding one security.
        if (a.value === null || b.value === null) return a.value === b.value ? a.index - b.index : a.value === null ? 1 : -1;
        const compared = text.has(selection.key) ? collator.compare(a.value, b.value) : a.value - b.value;
        return compared * direction || a.index - b.index;
      }).map(({item}) => item);
  }
  root.HoldingsSort = {sortRows, valueFor, isText: (key) => text.has(key), isMonetary: (key) => monetary.has(key)};
  if (typeof module !== "undefined" && module.exports) module.exports = root.HoldingsSort;
})(typeof globalThis !== "undefined" ? globalThis : this);
