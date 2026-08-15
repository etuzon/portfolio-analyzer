from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _LabelParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._label_depth = 0
        self.labeled_controls: set[str] = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "label":
            self._label_depth += 1
        elif self._label_depth and tag in {"input", "select", "textarea"} and values.get("id"):
            self.labeled_controls.add(values["id"])

    def handle_endtag(self, tag):
        if tag == "label" and self._label_depth:
            self._label_depth -= 1


def test_employee_stock_options_have_a_direct_guided_navigation_path():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    trigger = 'data-securities-workflow="employee-options"'
    assert trigger in html
    assert trigger in script
    assert 'id="employeeOptionsGuide"' in html
    assert 'id="employeeOptionsAccountNotice"' in html
    assert 'id="createEsopAccountFromOptions"' in html
    assert 'id="employeeOptionWizard"' in html
    assert 'data-employee-wizard-panel="1"' in html
    assert 'data-employee-wizard-panel="2"' in html
    assert 'data-employee-wizard-panel="3"' in html
    assert "The first vest happens" in html
    assert "months until all options are vested" in html
    assert 'data-edit-employee-option-grant=' in script
    assert 'data-delete-employee-option-grant=' in script
    assert 'api("/api/local/employee-option-grants")' in script


def test_employee_option_critical_inputs_have_visible_labels_and_status_feedback():
    html = (ROOT / "web/index.html").read_text()
    parser = _LabelParser()
    parser.feed(html)

    critical_controls = {
        "employeeWizardCompany",
        "employeeWizardGrantDate",
        "employeeWizardLocation",
        "employeeWizardCurrency",
        "employeeWizardExpiration",
        "employeeWizardStrikePrice",
        "employeeWizardAccount",
        "employeeWizardQuantity",
        "employeeWizardVestingStart",
        "employeeWizardVestingStyle",
    }
    assert critical_controls <= parser.labeled_controls
    assert 'id="employeeWizardGrantStatus" class="status-line" role="status" aria-live="polite"' in html
    assert 'id="employeeWizardVestingPreview" class="employee-wizard-preview" role="status" aria-live="polite"' in html
    assert 'id="employeeOptionWizardStatus" class="status-line" role="status" aria-live="polite"' in html


def test_employee_option_fields_stay_inside_their_grid_columns():
    styles = (ROOT / "web/styles.css").read_text()

    assert ".employee-wizard-grid > .management-field" in styles
    assert ".employee-wizard-grid > .management-field > input" in styles
    assert ".employee-wizard-grid > .management-field > select" in styles
    assert "max-width: 100%" in styles


def test_employee_option_grants_use_all_countries_and_three_supported_currencies():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    region_codes = script.split('const REGION_CODES = "', 1)[1].split('".split(" ");', 1)[0].split()

    assert 'id="manualSecurityLocation" autocomplete="country-name" required aria-required="true"' in html
    assert 'id="manualSecurityLocation" list="countryOptions"' not in html
    assert 'id="manualSecurityCurrency" required aria-required="true"' in html
    assert 'const SUPPORTED_MANAGEMENT_CURRENCIES = ["ILS", "USD", "EUR"]' in script
    assert "function companyCountryChoices()" in script
    assert "return REGION_CODES.map((code)" in script
    assert "PS" not in region_codes
    assert 'setCurrencyOptions("priceCurrency")' in script
    assert 'setCurrencyOptions("manualSecurityCurrency", isEmployeeOption ? SUPPORTED_MANAGEMENT_CURRENCIES : null)' in script
    assert "Employee stock-option currency must be ILS, USD, or EUR." in script


def test_account_forms_show_country_flags_and_three_supported_currencies():
    script = (ROOT / "web/app.js").read_text()

    assert 'const ACCOUNT_COUNTRY_CODES = { USA: "US", Israel: "IL" }' in script
    assert "function setAccountCountryOptions(selectId, preferred = \"\")" in script
    assert 'function bidiIsolate(value, direction = "auto")' in script
    assert '? `${countryName(code)} ${flagFor(code)}`' in script
    assert ': `${flagFor(code)} ${countryName(code)}`' in script
    assert 'bidiIsolate(label, "rtl")' in script
    assert '["localAccountLocation", "editAccountLocation", "brokerCountry"]' in script
    assert '.forEach((id) => setAccountCountryOptions(id, valueOf(id) || "USA"))' in script
    assert '["localAccountCurrency", "editAccountCurrency", "brokerCurrency", "employeeWizardCurrency"]' in script
    assert 'const HEBREW_CURRENCY_NAMES = { ILS: "שקל חדש", USD: "דולר אמריקאי", EUR: "אירו" }' in script
    assert '? `${currencyName(normalized)} ${currencySymbol(normalized)}`' in script
    assert 'function refreshLocalizedFormOptions()' in script
    assert '${countryDisplayLabel(broker.country)} · ${currencyDisplayLabel(broker.currency)}' in script
    assert '${esc(countryDisplayLabel(account.location))} · ${esc(currencyDisplayLabel(account.currency))}' in script


def test_account_creation_success_is_prominent_and_accessible():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert 'id="accountsStatus" class="status-line" role="status" aria-live="polite"' in html
    assert 'setStatusMessage("accountsStatus", "Account created", { prominentSuccess: true })' in script
    assert ".status-line.status-prominent-success" in styles
    assert "font-size: 16px" in styles


def test_date_picker_is_anchored_centerward_and_clamped_to_the_viewport():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert "function datePickerAnchorPosition(input)" in script
    assert "fieldCenter <= viewportWidth / 2" in script
    assert "rect.right + gap" in script
    assert "rect.left - estimatedPopupWidth - gap" in script
    assert "viewportWidth - estimatedPopupWidth - margin" in script
    assert "below + estimatedPopupHeight <= viewportHeight - margin" in script
    assert "positionNativeDatePicker(picker, input)" in script
    assert 'picker.style.insetInlineStart = "auto"' in script
    assert ".native-date-picker" in styles
    assert "inset-inline-start: 0" not in styles


def test_long_term_chart_can_include_or_exclude_pension_values():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert "longTermIncludePension: true" in script
    assert 'data-long-term-include-pension' in script
    assert 'String(fund.kind || "").trim().toLowerCase() !== "pension"' in script
    assert "state.longTermIncludePension = longTermPensionToggle.checked" in script
    assert "longTermIncludePension: state.longTermIncludePension" in script
    controls = script.split('<div class="long-term-control-row">', 1)[1].split('</div>\n          <div class="chart-legend', 1)[0]
    assert controls.index("${pensionToggle}") < controls.index('data-long-term-view="total"')
    assert ".long-term-pension-toggle" in styles
    assert '"Include pension": "הצג פנסיה"' in i18n
    assert '"Total": "סך הכל"' in i18n
    assert "סך הכול" not in i18n


def test_asset_mix_includes_cash_amount_and_percentage():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert "function portfolioCashValue()" in script
    assert 'groups.push({ label: "Cash", value: portfolioCashValue() })' in script
    assert "const assetGroups = assetMixGroups(items)" in script
    assert "const assetTotal = sum(assetGroups.map((group) => group.value)) || 1" in script
    assert 'group.label === "Cash" ? ` · ${money(group.value, state.baseCurrency, 0)}`' in script
    assert 'null, "asset-mix-card"' in script
    assert ".asset-mix-card .donut-legend" in styles
    assert "function currencyAllocationGroups(items)" in script
    assert "const cash = accountCashValue(account)" in script
    assert "totals[currency] = (totals[currency] || 0) + cash" in script
    assert "const currencyGroups = currencyAllocationGroups(items)" in script
    assert "const currencyTotal = sum(currencyGroups.map((group) => group.value)) || 1" in script
    assert "renderCurrencyAllocation(currencyGroups, currencyTotal)" in script
    assert '{ id: "cash_currency", title: "Cash by currency", view: "basic", size: "compact", area: "investments" }' in script
    assert "function cashByCurrencyData()" in script
    assert "const amount = Math.max(0, accountCashBalance(account))" in script
    assert "baseValue: normalizedAmount(amount, currency)" in script
    assert "function renderCashByCurrencyBars()" in script
    assert "cash_currency: () => renderCashByCurrencyBars()" in script
    assert ".cash-currency-bars" in styles


def test_market_banner_uses_dense_responsive_cards_without_smaller_text():
    styles = (ROOT / "web/styles.css").read_text()

    assert "grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));" in styles
    assert "grid-template-columns: repeat(3, minmax(150px, 1fr));" not in styles
    assert "gap: 8px" in styles
    assert ".ticker-card strong" in styles
    assert "font-size: 22px" in styles
    assert ".ticker-card .ticker-label" in styles
    assert "font-size: 12px" in styles


def test_account_value_trend_matches_portfolio_value_card_height():
    styles = (ROOT / "web/styles.css").read_text()

    assert ".portfolio-value-card,\n.account-trend-card {\n  min-height: 352px;" in styles
    assert ".account-trend-card {\n  display: grid;\n  grid-template-rows: auto minmax(0, 1fr);" in styles


def test_dashboard_header_does_not_repeat_overview_label():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    topbar = html.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
    assert '<p class="eyebrow">Overview</p>' not in topbar
    assert "Portfolio analyzer" in topbar
    assert '<button class="nav-item active" type="button">Home</button>' in html
    assert 'overview: "ראשי"' in script
    assert '"Home": "ראשי"' in i18n


def test_missing_stock_market_is_explicitly_not_available():
    script = (ROOT / "web/app.js").read_text()

    market_display = script.split("function stockMarketDisplay", 1)[1].split("\n}", 1)[0]
    assert 'optionLabel("Not available")' in market_display
    assert 'return candidate ? cleanSourceLabel(candidate).toUpperCase() : "Unknown"' not in market_display


def test_saved_security_history_is_visible_in_status_and_settings():
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert 'String(value).toLowerCase().includes("stale")' in script
    assert "Saved local history:" in script
    assert '["Saved security snapshots", data.security_snapshots ?? 0]' in script
    assert '["Securities with saved history", data.security_symbols ?? 0]' in script
    assert '"Saved security snapshots": "תמונות מצב שמורות של ניירות ערך"' in i18n
    assert '/^Saved local history:' in i18n


def test_risk_explanation_distinguishes_single_holding_from_symbol_concentration():
    script = (ROOT / "web/app.js").read_text()

    assert 'return `the largest single holding is ${text.slice(12)} of total value, including cash`' in script
    assert 'return `after combining holdings with the same symbol, one security is ${text.slice(21)} of securities value, excluding cash`' in script
    assert "const issuerRiskTotals = rows.reduce" in script
    assert "const symbolTotals = rows.reduce" in script
    assert "const largestIssuerRiskPct =" in script
    assert "const largestSymbolPct =" in script
    assert 'largestSymbolPct > 25 ? `Symbol concentration ${fmt(largestSymbolPct, 1)}%`' in script


def test_employee_option_workflow_filters_to_esop_accounts_and_employee_grants():
    script = (ROOT / "web/app.js").read_text()

    assert 'String(account.type || "").toUpperCase() === "ESOP"' in script
    assert 'item.instrument_type === "EMPLOYEE_STOCK_OPTION"' in script
    assert 'tx.instrument_type === "EMPLOYEE_STOCK_OPTION"' in script
    assert "setEmployeeOptionGuideStep(2)" in script


def test_dashboard_can_filter_cards_by_financial_area_and_detail_level():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert 'aria-label="Dashboard area"' in html
    assert 'data-dashboard-area="all"' in html
    assert 'data-dashboard-area="investments"' in html
    assert 'data-dashboard-area="long_term"' in html
    assert 'data-dashboard-area="employee"' in html
    assert 'data-dashboard-mode="basic"' in html
    assert 'data-dashboard-mode="expanded"' in html
    assert 'area: "all"' in script
    assert 'const DASHBOARD_AREAS = ["all", "investments", "long_term", "employee"]' in script
    assert 'employee: ["equity_comp"]' in script
    assert 'base.area = DASHBOARD_AREAS.includes(saved.area) ? saved.area : base.area' in script
    assert "function setDashboardArea(area)" in script
    assert 'button.setAttribute("aria-pressed", String(active))' in script
    assert ".dashboard-area-filter" in styles
    assert '"Investment portfolio": "תיק השקעות"' in i18n
    assert '"Long-term savings": "חיסכון לטווח ארוך"' in i18n
    assert '"Employee shares and options": "מניות ואופציות לעובדים"' in i18n


def test_sidebar_brand_shows_the_runtime_application_version():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert 'class="brand-name">Portfolio</span>' in html
    assert 'id="brandVersion" class="brand-version"' in html
    assert "async function loadBrandVersion()" in script
    assert 'const about = await api("/api/about")' in script
    assert 'loadBrandVersion().catch(() => {})' in script
    assert ".brand-version" in styles


def test_portfolio_loading_keeps_the_shell_and_forms_non_blocking():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert 'id="loadingOverlay" class="loading-overlay" role="status"' in html
    assert "if (overlay) overlay.hidden = true" in script
    assert "overlay.hidden = false" not in script
    assert '$("refresh")?.classList.toggle("is-loading", loadingRequests > 0)' in script


def test_modals_support_keyboard_focus_and_return_to_the_trigger():
    script = (ROOT / "web/app.js").read_text()

    assert "const modalReturnFocus = new Map()" in script
    assert 'document.querySelectorAll(".modal:not([hidden])")' in script
    assert 'if (event.key === "Escape")' in script
    assert "closeModal(activeModal)" in script
    assert 'activeModal.querySelectorAll(\'button:not([disabled])' in script
    assert '$("employeeWizardCompany")?.focus()' in script
    assert 'data-securities-workflow="employee-options"' in script
