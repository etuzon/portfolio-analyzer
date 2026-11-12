/* Pure browsing helpers for saved transactions. No requests or ledger writes. */
(function (root) {
  "use strict";

  const sortKeys = new Set(["date", "security", "account", "action", "quantity"]);
  const text = (value) => String(value ?? "").trim();
  const folded = (value) => text(value).normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase();

  function defaults() {
    return { query: "", account: "", action: "", from: "", to: "", sort: "date", direction: "desc" };
  }

  function displayAction(tx) {
    return text(text(tx?.comments).match(/^Imported source\s+(BUY|SELL|SHORT|ADD|REMOVE)\b/iu)?.[1] || tx?.action).toUpperCase();
  }

  function accountKey(tx) {
    const id = text(tx?.account_db_id);
    return id ? `id:${id}` : `legacy:${JSON.stringify([text(tx?.management_company), text(tx?.account_id)])}`;
  }

  function accountLabel(tx) {
    return [tx?.management_company, tx?.account_id].map(text).filter(Boolean).join(" · ");
  }

  // Accept storage/native-input ISO dates and the application's dd/mm/yyyy input.
  // Round-trip validation prevents invalid dates silently rolling into another month.
  function dateKey(value) {
    const source = text(value);
    const iso = source.match(/^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/u);
    const local = source.match(/^(\d{2})\/(\d{2})\/(\d{4})$/u);
    if (!iso && !local) return "";
    const [year, month, day] = iso ? iso.slice(1).map(Number) : [Number(local[3]), Number(local[2]), Number(local[1])];
    if (year < 1000 || month < 1 || month > 12 || day < 1 || day > 31) return "";
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) return "";
    return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  function accountOptions(rows, language = "en") {
    const options = new Map();
    for (const tx of rows || []) {
      const key = accountKey(tx);
      if (!options.has(key)) options.set(key, { value: key, label: accountLabel(tx) });
    }
    const collator = new Intl.Collator(language === "he" ? "he" : "en", { numeric: true, sensitivity: "base" });
    return [...options.values()].sort((a, b) => collator.compare(a.label, b.label) || collator.compare(a.value, b.value));
  }

  function filterAndSort(rows, selection = {}, language = "en", adapters = {}) {
    const filters = { ...defaults(), ...selection };
    const tokens = folded(filters.query).split(/\s+/u).filter(Boolean);
    const action = text(filters.action).toUpperCase();
    const from = dateKey(filters.from), to = dateKey(filters.to);
    const key = sortKeys.has(filters.sort) ? filters.sort : "date";
    const direction = filters.direction === "asc" ? 1 : -1;
    const collator = new Intl.Collator((selection.language || language) === "he" ? "he" : "en", { numeric: true, sensitivity: "base" });
    const selected = (rows || []).map((tx, index) => ({ tx, index })).filter(({ tx }) => {
      if (filters.account && accountKey(tx) !== filters.account) return false;
      if (action && text(tx.action).toUpperCase() !== action && displayAction(tx) !== action) return false;
      const date = dateKey(tx.trade_date);
      if ((from && (!date || date < from)) || (to && (!date || date > to))) return false;
      if (!tokens.length) return true;
      const haystack = folded([
        tx.symbol, tx.secondary_symbol, tx.security_name, tx.company_name,
        tx.public_symbol, tx.isin, tx.cusip, tx.comments,
      ].map(text).join(" "));
      return tokens.every((token) => haystack.includes(token));
    });

    function value(tx) {
      switch (key) {
        case "security": return text(tx.symbol || tx.company_name || tx.security_name) || null;
        case "account": return accountLabel(tx) || null;
        case "action": return (adapters.actionLabel?.(displayAction(tx)) || displayAction(tx)) || null;
        case "quantity": return typeof tx.quantity !== "boolean" && tx.quantity !== null && tx.quantity !== undefined && text(tx.quantity) !== "" && Number.isFinite(Number(tx.quantity)) ? Number(tx.quantity) : null;
        default: return dateKey(tx.trade_date) || null;
      }
    }

    return selected.map((row) => ({ ...row, value: value(row.tx) })).sort((a, b) => {
      // Missing values stay last in either direction. Equal primary values use
      // created/id chronology in the chosen direction, then original order.
      if (a.value === null || b.value === null) {
        return a.value === b.value ? a.index - b.index : a.value === null ? 1 : -1;
      } else {
        const compared = key === "quantity" ? a.value - b.value : collator.compare(a.value, b.value);
        if (compared) return compared * direction;
      }
      return collator.compare(text(a.tx.created_at), text(b.tx.created_at)) * direction
        || collator.compare(text(a.tx.id), text(b.tx.id)) * direction || a.index - b.index;
    }).map(({ tx }) => tx);
  }

  root.TransactionList = Object.freeze({ defaults, displayAction, accountKey, accountLabel, accountOptions, dateKey, filterAndSort });
  if (typeof module !== "undefined" && module.exports) module.exports = root.TransactionList;
})(typeof globalThis !== "undefined" ? globalThis : this);
