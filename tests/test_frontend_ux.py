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


def test_manual_securities_use_all_countries_and_only_three_supported_currencies():
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
    assert script.count('setCurrencyOptions("manualSecurityCurrency", SUPPORTED_MANAGEMENT_CURRENCIES)') == 2
    assert 'setCurrencyOptions("manualSecurityCurrency", isEmployeeOption ? SUPPORTED_MANAGEMENT_CURRENCIES : null)' not in script
    assert 'setCurrencyOptions("manualSecurityCurrency")' not in script
    assert "Security currency must be ILS, USD, or EUR." in script


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


def test_sidebar_starts_with_navigation_groups_without_a_redundant_main_menu_label():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    sidebar = html.split('<aside class="sidebar"', 1)[1].split('</aside>', 1)[0]
    assert "Main Menu" not in sidebar
    assert 'class="nav-title"' not in sidebar
    assert 't("mainMenu")' not in script
    assert 'mainMenu:' not in script
    assert ".nav-title" not in styles


def test_backup_files_use_one_compact_localized_line():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert 'function formatBackupDateTime(value)' in script
    assert '["Next run", backup.next_run ? formatBackupDateTime(backup.next_run) : "Disabled"]' in script
    assert 'optionLabel(file.type === "full" ? "Full backup · sensitive" : "Data-only backup")' in script
    assert '<bdi class="backup-file-name" dir="ltr">${esc(file.filename)}</bdi>' in script
    assert '<time datetime="${esc(file.modified_at || "")}" dir="ltr">${esc(formatBackupDateTime(file.modified_at))}</time>' in script
    assert '${esc(fmt(file.size_kb ?? 0, 1))} KB' in script
    assert '.setting-row.backup-file-row {' in styles
    backup_styles = styles.split('.setting-row.backup-file-row {', 1)[1].split('.settings-form {', 1)[0]
    assert 'grid-template-columns: minmax(0, 1fr) auto;' in backup_styles
    assert 'padding-block: 8px;' in backup_styles
    assert 'display: flex;' in backup_styles
    assert 'white-space: nowrap;' in backup_styles


def test_settings_use_a_section_menu_with_explanations_and_safe_full_restore():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    settings = html.split('id="settingsModal"', 1)[1].split('id="backupScheduleModal"', 1)[0]
    menu_labels = [
        "Display and language",
        "Table settings",
        "Portfolio data import and export",
        "Full backup and restore",
        "Cache and system status",
    ]
    assert all(label in settings for label in menu_labels)
    assert [settings.index(label) for label in menu_labels] == sorted(settings.index(label) for label in menu_labels)
    assert settings.count('class="settings-menu-help"') == 2
    assert 'aria-label="About portfolio data import and export"' in settings
    assert 'aria-label="About full backup and restore"' in settings
    assert 'id="settingsPanelDisplay"' in settings and 'data-settings-panel="display"' in settings
    assert 'id="settingsPanelBackup"' in settings and 'data-settings-panel="backup"' in settings
    assert 'id="fullRestoreFile" type="file" accept="application/zip,.zip" hidden' in settings
    assert 'function setSettingsSection(requestedSection = "display"' in script
    assert 'setSettingsSection("display", { focus: true })' in script
    assert '"/api/local/backups/inspect"' in script
    assert '"/api/local/backups/restore"' in script
    assert '"X-Restore-Confirm": "replace-current-application-state"' in script
    assert 'id="confirmFullRestoreRisk" type="checkbox"' in script
    assert '.settings-layout {' in styles
    assert '.settings-menu-help summary {' in styles
    assert '.full-restore-preview {' in styles
    assert '"Portfolio data import and export": "ייבוא וייצוא נתוני תיק"' in i18n
    assert '"Full backup and restore": "גיבוי ושחזור מלא"' in i18n


def test_settings_menu_is_keyboard_named_and_responsive():
    html = (ROOT / "web/index.html").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    script = (ROOT / "web/app.js").read_text()

    settings = html.split('id="settingsModal"', 1)[1].split('id="backupScheduleModal"', 1)[0]
    assert '<nav class="settings-menu" aria-label="Settings sections">' in settings
    assert settings.count('data-settings-section=') == 5
    assert settings.count('aria-controls="settingsPanel') == 5
    assert settings.count('aria-labelledby="settingsNav') == 5
    assert 'summary aria-label="About portfolio data import and export"' in settings
    assert 'summary aria-label="About full backup and restore"' in settings
    assert 'id="settingsStatus" class="status-line" role="status" aria-live="polite"' in settings
    assert 'id="fullRestorePreview" class="full-restore-preview" role="region" aria-live="polite" hidden' in settings
    assert 'if (restoreButton) restoreButton.disabled = !event.target.checked;' in script
    responsive = styles.split('@media (max-width: 760px) {', 1)[1]
    assert '.settings-layout {' in responsive
    assert 'grid-template-columns: 1fr;' in responsive
    assert '.settings-menu {' in responsive
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr));' in responsive


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


def test_rsu_is_a_transaction_grant_type_and_manual_securities_are_safely_editable():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    backend = (ROOT / "app/local_portfolio.py").read_text()

    assert 'Holding / grant type *' in html
    assert 'Choose RSU for shares granted by an employer' in html
    assert 'instrument_types: ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "EMPLOYEE_STOCK_OPTION"' in script
    assert 'const isRsu = String(valueOf("securityAssetClass") || "").toUpperCase() === "RSU"' in script
    assert 'data-edit-manual-security="${esc(item.id)}"' in script
    assert 'data-delete-manual-security="${esc(item.id)}"${removalDisabled ? " disabled" : ""}' in script
    assert 'class="row-action-help security-delete-help"' in script
    assert 'help.classList.toggle("open-up", availableBelow < popover.offsetHeight + 10)' in script
    assert '.row-action-help.open-up .row-action-help-popover {' in styles
    assert 'item.attachment_counts?.[key]' in script
    assert '["transactions", "Security transactions"]' in script
    assert '["price_history", "Saved price history"]' in script
    assert 'state.editingManualSecurityId = item.id' in script
    assert 'id: state.editingManualSecurityId || undefined' in script
    assert '.security-management-item {' in styles
    assert '.security-delete-help[open] {' in styles
    assert "set instrument_type = 'STOCK', asset_class = 'EQUITY'" in backend


def test_security_transaction_fields_stay_aligned_with_compact_help():
    html = (ROOT / "web/index.html").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    grant_field = html.split('id="securityAssetClass"', 1)[0].rsplit('<label class="management-field"', 1)[1]
    assert 'class="field-label"' in grant_field
    assert 'aria-label="Choose RSU for shares granted by an employer' in grant_field
    assert '>i</em>' in grant_field
    assert '<small>' not in grant_field
    assert '.transaction-form {\n  grid-template-columns: repeat(6, minmax(140px, 1fr));' in styles


def test_portfolio_filter_is_immediate_and_can_find_employee_securities():
    script = (ROOT / "web/app.js").read_text()

    apply_filter = script.split("function applyFilter()", 1)[1].split("\n}", 1)[0]
    assert 'state.portfolioFilterCriteria = criteriaFromForm()' in apply_filter
    assert 'filterPortfolioItems(state.allPortfolioItems' in apply_filter
    assert 'renderRows(matches)' in apply_filter
    assert '/api/screener' not in apply_filter
    assert 'state.allPortfolioItems = allItems' in script
    assert 'if (!hasActivePortfolioFilter(criteria)) return portfolioItems(items)' in script
    assert '[holding.symbol, holding.secondary_symbol, holding.name].some' in script
    assert 'event.target.id === "query" && event.key === "Enter"' in script


def test_equity_compensation_price_map_uses_all_holdings_and_both_symbols():
    script = (ROOT / "web/app.js").read_text()

    price_map = script.split("function compensationPriceMap", 1)[1].split("function publicStockMarket", 1)[0]
    assert "state.allPortfolioItems" in price_map
    assert "[h.symbol, h.secondary_symbol].filter(Boolean)" in price_map
    assert "prices.set(txMarketKey(symbol, h.stock_market), entry)" in price_map


def test_equity_compensation_table_explains_type_and_exposes_missing_price_action():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    table = script.split("function renderEquityCompTable", 1)[1].split("function renderEquityCompDashboard", 1)[0]
    assert table.index("<th>Instrument</th>") < table.index("<th>Investment type</th>") < table.index("<th>Market / strike price</th>")
    assert table.count("<th>") == 5
    assert 'class="equity-position-cell' in table
    assert 'class="equity-position-content"' in table
    assert 'equityCompPriceHtml(group)' in table
    assert 'data-price-history-symbol=' in script
    assert 'openPriceHistoryForSecurity(equityPriceTrigger.dataset, equityPriceTrigger)' in script
    assert 'openModal("pricesModal", returnFocus, { focusId: "priceInput" })' in script
    assert '.equity-price-cell {' in styles
    assert '"Instrument": "נייר ערך"' in i18n
    assert '"Investment type": "סוג השקעה"' in i18n
    assert '"Market / strike price": "מחיר שוק / מימוש"' in i18n
    assert '"Add market price": "הוספת מחיר שוק"' in i18n
    assert '[/^([\\d,.]+)\\s+RSU shares$/u' in i18n


def test_equity_compensation_table_stays_inside_its_dashboard_card():
    styles = (ROOT / "web/styles.css").read_text()

    card = styles.split(".equity-comp-card {", 1)[1].split("}", 1)[0]
    table_wrap = styles.split(".equity-comp-table-wrap {", 1)[1].split("}", 1)[0]
    table = styles.split(".equity-comp-table {", 1)[1].split("}", 1)[0]
    assert "height: auto;" in card
    assert "min-height: 250px;" in card
    assert "overflow: hidden;" in card
    assert "max-height: 260px;" in table_wrap
    assert "overflow-x: hidden;" in table_wrap
    assert "overflow-y: auto;" in table_wrap
    assert "min-width: 0;" in table
    position_content = styles.split(".equity-position-content {", 1)[1].split("}", 1)[0]
    muted_value = styles.split(".equity-position-content > .muted-inline {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: minmax(0, 1fr);" in position_content
    assert "text-overflow: ellipsis;" in muted_value
    assert "white-space: nowrap;" in muted_value


def test_optional_secondary_security_symbol_is_editable_visible_and_searchable():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()
    store = (ROOT / "app/local_portfolio.py").read_text()
    metrics = (ROOT / "app/metrics.py").read_text()

    assert 'id="manualSecondarySymbol" placeholder="Optional alternate ticker"' in html
    assert 'Optional alternate ticker used for market data, for example CEL for 1101534.' in html
    assert 'secondary_symbol: secondarySymbol' in script
    assert '$("manualSecondarySymbol").value = item.secondary_symbol || ""' in script
    assert 'holding.secondary_symbol, holding.name' in script
    assert 'class="secondary-symbol" title="Secondary symbol"' in script
    assert 'tx.secondary_symbol || tx.symbol' in script
    assert '.secondary-symbol {' in styles
    assert '"Secondary Symbol": "סימול משני"' in i18n
    assert '"secondary_symbol"' in store
    assert 'secondary_symbol text not null default \'\'' in store
    assert '"secondary_symbol": holding.secondary_symbol' in metrics
    assert '"stock_market": holding.stock_market' in metrics


def test_security_provider_label_prefers_the_provider_that_supplied_prices():
    script = (ROOT / "web/app.js").read_text()
    function = script[script.index("function dataProviderDisplay"):script.index("function bestCurrencyTotal")]

    assert 'key.startsWith("prices.")' in function
    assert function.index('if (provider) return providerDisplayName') < function.index('if (h.data_source')


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


def test_pension_owner_is_inherited_from_required_long_term_account():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert 'id="fundAccount" required' in html
    assert 'id="editFundAccount" required' in html
    assert 'id="fundAccountOwner"' in html
    assert 'id="editFundAccountOwner"' in html
    assert "fundFamilyMember" not in html
    assert "editFundFamilyMember" not in html
    assert "attachFundPerson" not in html
    assert "attachEditFundPerson" not in html
    assert "fundPersons" not in script
    assert "editFundPersons" not in script
    assert "renderFundAccountOwners()" in script
    assert 'account_id: valueOf("fundAccount")' in script


def test_fund_row_actions_stay_grouped_instead_of_wrapping_remove_into_the_middle():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    fund_row = script.split('<div class="stack-item management-item fund-management-item">', 1)[1].split('</div>\n    `;', 1)[0]
    actions = fund_row.split('<div class="row-actions fund-management-actions">', 1)[1].split('</div>', 1)[0]
    assert actions.index('data-fund-history=') < actions.index('data-edit-fund=') < actions.index('data-delete-fund=')
    assert '.fund-management-item,\n.account-management-item {\n  grid-template-columns: minmax(0, 1fr) auto;' in styles
    assert '.fund-management-actions,\n.account-management-actions {\n  align-self: start;\n  justify-content: flex-end;\n  flex-wrap: nowrap;' in styles
    mobile = styles.split('@media (max-width: 760px) {', 1)[1]
    assert '.fund-management-item,\n  .account-management-item {\n    grid-template-columns: 1fr;' in mobile
    assert '.fund-management-actions,\n  .account-management-actions {' in mobile
    assert 'flex-wrap: wrap;' in mobile.split('.fund-management-actions,\n  .account-management-actions {', 1)[1].split('}', 1)[0]


def test_account_remove_is_disabled_with_an_adjacent_attachment_explanation():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert 'class="row-actions account-management-actions"' in script
    assert 'data-delete-account="${esc(account.id)}"${removalDisabled ? " disabled" : ""}' in script
    assert 'class="row-action-help account-delete-help"' in script
    assert 'style="--attachment-rows:${attachmentRows.length}"' in script
    assert 'account.attachment_counts?.[key]' in script
    assert '["transactions", "Security transactions"]' in script
    assert '["funds", "Pension and fund records"]' in script
    assert '["account_snapshots", "Account history points"]' in script
    assert 'async function removeLocalAccount(accountId)' in script
    assert '.row-action-help-popover {' in styles
    assert '.account-management-actions {\n  align-items: flex-start;\n}' in styles
    assert '.account-delete-help[open] {' in styles
    assert 'margin-block-end: calc(72px + var(--attachment-rows, 1) * 21px);' in styles
    assert '"Why account removal is disabled": "למה הסרת החשבון מושבתת"' in i18n


def test_external_account_id_is_explicitly_optional_and_never_filled_from_internal_uuid():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    backend = (ROOT / "app/local_portfolio.py").read_text()

    assert html.count("Account ID (optional)") >= 4
    assert 'return parts.join(" · ") || optionLabel("Unnamed account");' in script
    assert 'record["account_id"] = account_id[:8]' not in backend


def test_account_owner_rules_and_partial_import_recovery_are_visible():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert "Every account needs at least one person" in html
    assert 'id="importSkippedList"' in html
    assert '!["Long-Term Savings", "ESOP"].includes(account?.type)' in script
    assert "function validateAccountOwnership" in script
    assert "function renderImportSkippedAccounts" in script
    assert "function prepareSkippedImportAccount" in script
    assert 'data-add-skipped-account' in script
    assert "Import completed with errors" in script


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
