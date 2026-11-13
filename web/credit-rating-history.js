/* Research detection times never become invented agency action dates. */
function creditRatingHistoryValue(status, rating) {
  if (status === "rated" && rating) return String(rating);
  return t({ unrated: "Unrated", withdrawn: "Withdrawn", conflicting: "Conflicting evidence", unavailable: "Unavailable",
    not_found: "Not found", not_checked: "Unknown" }[status] || "Unknown");
}

function creditRatingHistoryEventLabel(event) {
  return t({ first_observation: "First recorded", rating_change: "Rating changed", outlook_change: "Outlook changed", watch_change: "Watch changed",
    manual_added: "Manual entry added", manual_updated: "Manual entry updated", manual_cleared: "Manual override cleared" }[event.event_type]
    || (event.origin === "manual" ? "Manual entry updated" : "Rating observation"));
}

function creditRatingHistoryDateLabel(event) {
  if (event.origin === "manual" || event.date_basis === "manual_entry") return "Manual entry date";
  return event.date_basis === "agency_action" && event.change_date ? "Agency action date" : "Detected at";
}

function creditRatingHistoryDate(event) {
  return creditRatingsDate(event.origin !== "manual" && event.date_basis === "agency_action" && event.change_date ? event.change_date : event.detected_at);
}

function creditRatingHistoryChanges(event) {
  const fields = Array.isArray(event.changed_fields) ? event.changed_fields : [];
  if (event.event_type === "first_observation" || event.event_type === "manual_added" && !event.previous_status) return [{ label: "Credit rating", previous: null, current: creditRatingHistoryValue(event.new_status, event.new_rating) }];
  const changes = [];
  const previous = creditRatingHistoryValue(event.previous_status, event.previous_rating), current = creditRatingHistoryValue(event.new_status, event.new_rating);
  if (event.event_type === "rating_change" || previous !== current && (fields.includes("rating") || fields.includes("status") || event.origin === "manual")) changes.push({ label: "Credit rating", previous, current });
  if (event.event_type === "outlook_change" || fields.includes("outlook")) changes.push({ label: "Outlook", previous: creditRatingsDirection(event.previous_outlook), current: creditRatingsDirection(event.new_outlook) });
  if (event.event_type === "watch_change" || fields.includes("watch")) changes.push({ label: "Watch", previous: creditRatingsDirection(event.previous_watch, true), current: creditRatingsDirection(event.new_watch, true) });
  return changes;
}

function creditRatingHistoryTransitionHtml(change) {
  return `<bdi class="credit-history-transition" dir="ltr">${change.previous !== null ? `<bdi dir="auto">${esc(change.previous)}</bdi><span aria-hidden="true"> → </span><span class="sr-only"> ${esc(t("to"))} </span>` : ""}<bdi dir="auto">${esc(change.current)}</bdi></bdi>`;
}

function creditRatingLatestChangeText(event) {
  if (!event) return "";
  const transitions = creditRatingHistoryChanges(event).map((change) => `${t(change.label)}: ${change.previous !== null ? `${change.previous} → ` : ""}${change.current}`);
  return [creditRatingHistoryEventLabel(event), ...transitions, `${t(creditRatingHistoryDateLabel(event))}: ${creditRatingHistoryDate(event)}`].join(" · ");
}

function creditRatingLatestChangeHtml(record) {
  const event = record?.latest_change;
  if (!event) return "";
  const changes = creditRatingHistoryChanges(event);
  const grade = changes.find((change) => change.label === "Credit rating");
  const manual = event.origin === "manual";
  const transition = event.event_type !== "first_observation" && grade?.previous !== null && grade ? creditRatingHistoryTransitionHtml(grade) : "";
  const label = event.event_type === "first_observation" ? `${creditRatingHistoryEventLabel(event)} · ${t("Detected at")}` : manual ? creditRatingHistoryEventLabel(event)
    : event.date_basis === "agency_action" && event.change_date ? t("Changed") : t("Detected at");
  return `<span class="holding-credit-change" data-credit-latest-change="${esc(event.event_id || "")}" title="${esc(creditRatingLatestChangeText(event))}">${transition}${transition ? " · " : ""}${esc(label)} ${esc(creditRatingHistoryDate(event))}</span>`;
}

function renderCreditRatingHistory(context, prefix = "securityCreditRatingHistory") {
  const panel = $(prefix), list = $(`${prefix}List`);
  if (!panel || !list) return;
  panel.hidden = !context;
  if (!context) return;
  const events = Array.isArray(context.rating_history) ? context.rating_history : [];
  const empty = $(`${prefix}Empty`);
  empty.hidden = Boolean(events.length);
  empty.textContent = t("No rating history has been recorded yet. A saved current rating does not establish its earlier history.");
  list.hidden = !events.length;
  const scrollTop = list.scrollTop, focusedKey = document.activeElement?.dataset?.creditHistorySource;
  const html = events.map((event) => {
    const agency = { moodys: "Moody’s", sp: "S&P Global Ratings", fitch: "Fitch" }[event.agency] || t("Unknown");
    const changes = creditRatingHistoryChanges(event);
    const scope = t({ issuer: "Issuer rating", issue: "Issue rating", sovereign: "Sovereign credit rating" }[event.scope] || "Unknown");
    const scale = t({ global: "Global scale", national: "National scale" }[event.scale] || "Unknown");
    const term = t({ long_term: "Long term", short_term: "Short term" }[event.term] || "Unknown");
    const metadata = [["Rated entity", event.entity_name || t("Unknown")], ["Rating scope", scope], ["Rating scale", scale], ["Rating term", term],
      [creditRatingHistoryDateLabel(event), creditRatingHistoryDate(event)]];
    if (event.rating_type) metadata.push(["Rating category", creditRatingsCategory(event)]);
    if (event.currency_basis) metadata.push(["Rating currency basis", t({ local_currency: "Local currency", foreign_currency: "Foreign currency", local: "Local currency", foreign: "Foreign currency" }[event.currency_basis] || "Unknown")]);
    if (event.date_basis === "agency_action" && event.detected_at) metadata.push(["Detected at", creditRatingsDate(event.detected_at)]);
    if (event.actor) metadata.push(["Updated by", event.actor]);
    for (const [field, label] of [["rating_date", "Rating date"], ["outlook_date", "Outlook date"], ["watch_date", "Watch date"]]) if (event[field]) metadata.push([label, creditRatingsDate(event[field])]);
    const seen = new Set();
    const sources = (Array.isArray(event.sources) ? event.sources : []).flatMap((source) => {
      const url = creditRatingsSourceUrl(source.url);
      if (!url || seen.has(url)) return [];
      seen.add(url);
      const key = `${event.event_id || "event"}:${seen.size}`;
      return [`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" data-credit-history-source="${esc(key)}">${esc(t("Source {number}").replace("{number}", String(seen.size)))}</a>`];
    });
    return `<li data-credit-history-event="${esc(event.event_id || "")}"><div class="credit-history-heading"><bdi dir="ltr">${esc(agency)}</bdi><strong>${esc(creditRatingHistoryEventLabel(event))}</strong><span class="badge neutral">${esc(t(event.origin === "manual" ? "Manual" : "Public source research"))}</span></div>${changes.map((change) => `<p>${esc(t(change.label))}: ${creditRatingHistoryTransitionHtml(change)}</p>`).join("")}<dl>${metadata.map(([label, value]) => `<div><dt>${esc(t(label))}</dt><dd><bdi dir="auto">${esc(value)}</bdi></dd></div>`).join("")}</dl>${sources.length ? `<div class="credit-rating-sources">${sources.join(" ")}</div>` : ""}${event.origin === "manual" ? `<p class="section-note">${esc(t("This records a manual edit, not an agency rating action."))}</p>` : ""}</li>`;
  }).join("");
  if (list.innerHTML !== html) {
    list.innerHTML = html;
    list.scrollTop = scrollTop;
    if (focusedKey) [...list.querySelectorAll("[data-credit-history-source]")].find((node) => node.dataset.creditHistorySource === focusedKey)?.focus({ preventScroll: true });
  }
}
