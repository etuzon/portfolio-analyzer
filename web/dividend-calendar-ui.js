let dividendCalendarView = {version:0, data:null, loading:false, error:"", selected:""};

function resetDividendCalendar() {
  dividendCalendarView = {version:dividendCalendarView.version + 1, data:null, loading:false, error:"", selected:""};
  if ($("dividendCalendarAccount")) $("dividendCalendarAccount").innerHTML = `<option value="">${esc(t("Any account"))}</option>`;
  if ($("dividendCalendarYear")) $("dividendCalendarYear").innerHTML = "";
  renderDividendCalendar();
}

function dividendCalendarListing(asset) { return [asset.symbol, asset.stock_market].filter(Boolean).join(" · "); }
function dividendCalendarDateType(event) {
  return t({payment:"Payment date", ex_date:"Ex-dividend date; payment date unavailable", provider_date:"Provider date; payment date unknown", ledger:"Recorded ledger date"}[event.date_type] || "Date unavailable");
}
function dividendCalendarMoney(value, currency) {
  return value === null || value === undefined || !currency ? esc(t("Unavailable")) : esc(money(value, currency, 4));
}
function dividendCalendarYield(asset) {
  return asset.annual_yield_percent === null ? t("Annual yield unavailable") : `${fmt(asset.annual_yield_percent, 2)}%`;
}
function dividendCalendarInlineText(event, asset) {
  const yearly = asset.year_dividend_per_share === null || !asset.currency ? t("Unavailable") : money(asset.year_dividend_per_share, asset.currency, 4);
  const source = event.date_type === "ledger" ? t("Recorded transactions") : asset.source ? providerDisplayName(asset.source) : t("Unknown");
  return `${t("Known year dividends / share")}: ${yearly} · ${t("Source")}: ${source}`;
}
function dividendCalendarLimits(asset) {
  const labels = [];
  if (asset.currency_conflict) labels.push("Conflicting security currencies");
  if (asset.history_partial) labels.push("Partial dividend history");
  if (asset.history_stale) labels.push("Dividend evidence older than 30 days or undated");
  if (asset.price_stale) labels.push("Price older than 7 days or missing");
  if (asset.invalid_prices) labels.push("Incompatible local-price currencies excluded");
  return labels.map(label => t(label)).join(" · ");
}

function renderDividendCalendar() {
  const target = $("dividendCalendarResults");
  if (!target) return;
  const view = dividendCalendarView, data = view.data;
  const account = $("dividendCalendarAccount"), chosen = account.value;
  const yearSelect = $("dividendCalendarYear");
  const year = Number(yearSelect.value || new Date().getFullYear());
  const years = data?.available_years || [year - 2, year - 1, year, year + 1];
  yearSelect.innerHTML = [...new Set([...years, year])].sort((a,b)=>b-a).map(value => `<option value="${value}">${value}</option>`).join("");
  yearSelect.value = String(year);
  if (data) {
    account.innerHTML = `<option value="">${esc(t("Any account"))}</option>` + data.accounts.map(row => `<option value="${esc(row.id)}">${esc(accountLabel(row))}</option>`).join("");
    account.value = chosen;
  }
  target.setAttribute("aria-busy", String(view.loading));
  $("dividendCalendarReload").disabled = view.loading;
  $("dividendCalendarStatus").textContent = t(view.loading ? "Reading saved dividend data…" : view.error);
  if (!data || data.account_id !== chosen || data.year !== year) { target.innerHTML = ""; $("dividendCalendarDetails").innerHTML = ""; return; }
  if (!data.assets.length) {
    target.innerHTML = `<p>${esc(t("No eligible long stock or fund holdings in this account scope."))}</p>`;
    $("dividendCalendarDetails").innerHTML = "";
    return;
  }
  const assets = new Map(data.assets.map(asset => [asset.id, asset]));
  const maxYield = Math.max(0, ...data.assets.map(asset => Number(asset.annual_yield_percent) || 0));
  const eventsByMonth = Array.from({length:12}, () => []);
  data.events.forEach(event => eventsByMonth[Number(event.date.slice(5,7))-1].push(event));
  const eventButton = event => {
    const asset = assets.get(event.asset_id);
    const known = asset.annual_yield_percent !== null;
    const size = known && maxYield > 0 ? Math.max(7, 26 * Math.sqrt(asset.annual_yield_percent / maxYield)) : 12;
    const amount = event.date_type === "ledger" ? dividendCalendarMoney(event.recorded_amount, event.currency) : `${dividendCalendarMoney(event.amount_per_share, event.currency)} / ${esc(t("share"))}`;
    const description = `${dividendCalendarListing(asset)} · ${formatDate(event.date)} · ${dividendCalendarDateType(event)} · ${event.date_type === "ledger" ? money(event.recorded_amount, event.currency, 4) : `${money(event.amount_per_share, event.currency, 4)} / ${t("share")}`} · ${dividendCalendarYield(asset)}${asset.highest_yield ? ` · ${t("Highest annual yield")}` : ""}${event.future ? ` · ${t("Reported future date")}` : ""}`;
    return `<button type="button" class="dividend-calendar-entry${asset.highest_yield ? " highest-yield" : ""}" data-dividend-calendar-event="${esc(event.id)}" aria-pressed="${String(view.selected === event.id)}" aria-label="${esc(description)}">
      <span class="dividend-yield-dot${known ? "" : " unknown-yield"}" style="--yield-size:${size}px" aria-hidden="true"></span>
      <span class="dividend-event-content"><strong><bdi>${esc(asset.symbol)}</bdi> · ${esc(dividendCalendarYield(asset))}</strong><span>${esc(formatDate(event.date))} · ${amount}</span><small>${esc(dividendCalendarDateType(event))}${event.future ? ` · ${esc(t("Reported future date"))}` : ""}</small>${asset.highest_yield ? `<small class="dividend-highest-label">★ ${esc(t("Highest annual yield"))}</small>` : ""}${!asset.rankable && known ? `<small>${esc(t("Limited comparison data"))}</small>` : ""}${view.selected === event.id ? `<small class="dividend-inline-detail">${esc(dividendCalendarInlineText(event, asset))}</small>` : ""}</span></button>`;
  };
  const monthCards = eventsByMonth.map((events, month) => `<section class="dividend-month" aria-labelledby="dividendMonth${month}"><h3 id="dividendMonth${month}">${esc(new Intl.DateTimeFormat(state.language === "he" ? "he-IL" : "en-GB", {month:"long"}).format(new Date(year, month, 1)))}</h3>${events.length ? events.map(eventButton).join("") : `<p class="section-note">${esc(t("No dated dividend records"))}</p>`}</section>`).join("");
  const facts = asset => [
    ["Known year dividends / share", `${dividendCalendarMoney(asset.year_dividend_per_share, asset.currency)}<small>${asset.year_payment_count} ${esc(t("reported distributions"))}</small>`],
    ["Observed last 12 months / share", dividendCalendarMoney(asset.ttm_dividend_per_share, asset.currency)],
    ["Annual dividend yield", `${esc(dividendCalendarYield(asset))}${asset.highest_yield ? `<small class="dividend-highest-label">★ ${esc(t("Highest annual yield"))}</small>` : ""}`],
    ["Saved price used", `${dividendCalendarMoney(asset.price, asset.currency)}${asset.price_date ? `<small>${esc(formatDate(asset.price_date))}</small>` : ""}`],
    ["Recorded year income", asset.recorded_income.length ? asset.recorded_income.map(row => dividendCalendarMoney(row.amount, row.currency)).join("<br>") : esc(t("No recorded income"))],
  ];
  const rows = data.assets.map(asset => `<tr><th scope="row"><bdi>${esc(dividendCalendarListing(asset))}</bdi>${asset.name ? `<small dir="auto">${esc(asset.name)}</small>` : ""}<small>${esc(dividendCalendarLimits(asset))}</small></th>${facts(asset).map(([,html]) => `<td>${html}</td>`).join("")}</tr>`).join("");
  const mobile = `<ul class="dividend-annual-cards">${data.assets.map(asset => `<li><h4><bdi>${esc(dividendCalendarListing(asset))}</bdi></h4><dl>${facts(asset).map(([label,html]) => `<dt>${esc(t(label))}</dt><dd>${html}</dd>`).join("")}</dl><p class="section-note">${esc(dividendCalendarLimits(asset))}</p></li>`).join("")}</ul>`;
  target.innerHTML = `<p class="section-note">${esc(t("Current annual-yield comparison"))}: <bdi dir="ltr">${esc(formatDate(data.ttm_from))} – ${esc(formatDate(data.ttm_to))}</bdi>. ${esc(t("This comparison stays current when viewing a historical calendar year."))}</p>
    <div class="dividend-calendar-grid">${monthCards}</div>
    <h3>${esc(t("Annual dividend summary"))} · ${year}</h3><div class="table-wrap dividend-annual-scroll" tabindex="0" role="region" aria-label="${esc(t("Annual dividend summary"))}"><table class="dividend-annual-table"><thead><tr><th scope="col">${esc(t("Security"))}</th>${facts(data.assets[0]).map(([label])=>`<th scope="col">${esc(t(label))}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>${mobile}
    <details class="dividend-coverage"><summary>${esc(t("Dividend data coverage"))}</summary><ul>${data.assets.map(asset => `<li><bdi>${esc(dividendCalendarListing(asset))}</bdi> · ${esc(asset.source ? providerDisplayName(asset.source) : t("No saved dividend history"))}<br>${esc(t("Saved evidence date"))}: ${asset.fetched_date ? esc(formatDate(asset.fetched_date)) : esc(t("Unknown"))} · ${esc(t("History dates"))}: ${asset.history_from ? `<bdi dir="ltr">${esc(formatDate(asset.history_from))} – ${esc(formatDate(asset.history_to))}</bdi>` : esc(t("Unknown"))}<br>${asset.undated_records} ${esc(t("undated records"))} · ${asset.invalid_records} ${esc(t("invalid or incompatible records excluded"))}</li>`).join("")}</ul></details>
    ${data.excluded.length ? `<p class="section-note">${data.excluded.length} ${esc(t("short or unsupported holdings excluded"))}: ${data.excluded.map(row => `<bdi>${esc(row.symbol)} · ${esc(row.stock_market)}</bdi>`).join(", ")}</p>` : ""}`;
  renderDividendCalendarDetails();
}

function renderDividendCalendarDetails() {
  const target = $("dividendCalendarDetails"), view = dividendCalendarView;
  if (!target) return;
  const event = view.data?.events.find(row => row.id === view.selected);
  const asset = event && view.data.assets.find(row => row.id === event.asset_id);
  if (!asset) { target.innerHTML = ""; return; }
  target.innerHTML = `<h3><bdi>${esc(dividendCalendarListing(asset))}</bdi> · ${esc(formatDate(event.date))}</h3><p>${esc(dividendCalendarDateType(event))} · ${event.date_type === "ledger" ? `${esc(t("Recorded dividend income"))}: ${dividendCalendarMoney(event.recorded_amount, event.currency)}` : `${esc(t("Dividend per share"))}: ${dividendCalendarMoney(event.amount_per_share, event.currency)}`}</p><p>${esc(dividendCalendarInlineText(event, asset))} · ${esc(t("Annual dividend yield"))}: ${esc(dividendCalendarYield(asset))}</p><p class="section-note">${esc(dividendCalendarLimits(asset))}</p>`;
}

async function loadDividendCalendar() {
  const version = ++dividendCalendarView.version;
  dividendCalendarView.loading = true; dividendCalendarView.error = "";
  const params = new URLSearchParams({account_id:$("dividendCalendarAccount").value, year:$("dividendCalendarYear").value || String(new Date().getFullYear())});
  renderDividendCalendar();
  try {
    const data = await api(`/api/portfolio/dividend-calendar?${params}`);
    if (version !== dividendCalendarView.version) return;
    dividendCalendarView.data = data; dividendCalendarView.selected = "";
  } catch {
    if (version !== dividendCalendarView.version) return;
    dividendCalendarView.error = "Could not load the dividend calendar. Use Reload to retry.";
  }
  if (version !== dividendCalendarView.version) return;
  dividendCalendarView.loading = false;
  renderDividendCalendar();
}

document.addEventListener("change", event => { if (["dividendCalendarAccount", "dividendCalendarYear"].includes(event.target.id)) loadDividendCalendar(); });
document.addEventListener("click", event => {
  if (event.target.closest("#dividendCalendarReload")) loadDividendCalendar();
  const button = event.target.closest("[data-dividend-calendar-event]");
  if (button) {
    dividendCalendarView.selected = button.dataset.dividendCalendarEvent;
    document.querySelectorAll("[data-dividend-calendar-event]").forEach(node => node.setAttribute("aria-pressed", String(node === button)));
    document.querySelectorAll(".dividend-inline-detail").forEach(node => node.remove());
    const selected = dividendCalendarView.data?.events.find(row => row.id === dividendCalendarView.selected);
    const asset = selected && dividendCalendarView.data.assets.find(row => row.id === selected.asset_id);
    if (asset) {
      const inline = document.createElement("small");
      inline.className = "dividend-inline-detail";
      inline.textContent = dividendCalendarInlineText(selected, asset);
      button.querySelector(".dividend-event-content")?.append(inline);
    }
    renderDividendCalendarDetails();
  }
});
