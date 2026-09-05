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


def test_dashboard_shows_bond_market_value_grouped_by_currency():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert '{ id: "bond_currency", title: "Bonds by currency", view: "basic", size: "compact", area: "investments" }' in script
    assert 'investments: ["portfolio_value", "account_trend", "asset_mix", "top_holdings", "bond_currency"]' in script
    assert "function bondsByCurrencyData(items)" in script
    assert "[holding.asset_class, holding.asset_sub_class]" in script
    assert "group.amount += Number(holding.market_value || 0)" in script
    assert "baseValue: normalizedAmount(group.amount, group.currency)" in script
    assert "function renderBondsByCurrency(items)" in script
    assert "bond_currency: () => renderBondsByCurrency(items)" in script
    assert ".bond-currency-card" in styles
    assert ".bond-currency-bars" in styles
    assert '"Bonds by currency": "אג״ח לפי מטבע"' in i18n
    assert '"No bond holdings": "אין אחזקות אג״ח"' in i18n


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


def test_help_menu_covers_every_navigation_group_with_accessible_submenus():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    sidebar = html.split('<aside class="sidebar"', 1)[1].split("</aside>", 1)[0]
    system_menu = sidebar.split("<summary>System</summary>", 1)[1].split("</details>", 1)[0]
    help_menu = sidebar.split("<summary>Help</summary>", 1)[1].split("</details>", 1)[0]
    assert 'data-modal="settingsModal">Settings</button>' in system_menu
    assert 'data-modal="aboutModal"' not in system_menu
    assert 'data-modal="aboutModal">About</button>' in help_menu
    assert 'data-modal="helpModal">Help</button>' in help_menu
    assert help_menu.index('data-modal="aboutModal"') < help_menu.index('data-modal="helpModal"')

    help_dialog = html.split('id="helpModal"', 1)[1].split('id="securityDetailModal"', 1)[0]
    assert 'role="dialog" aria-modal="true" aria-labelledby="helpTitle" aria-describedby="helpIntro"' in help_dialog
    assert 'data-modal-initial-focus aria-label="Close"' in help_dialog
    assert help_dialog.count('<details class="help-group"') == 8
    assert '<details class="help-group" open>' in help_dialog
    for group in ["Dashboard", "Portfolio Data", "People", "Retirement", "Research", "Markets", "System", "Help"]:
        assert f"<summary><span>{group}</span>" in help_dialog
    for feature in [
        "Home", "Reports", "Accounts", "Brokers", "Employee Stock Options", "Securities", "Prices", "Events",
        "Family Members", "Account Ownership", "Pensions &amp; Funds", "Retirement Projections", "Company Reports",
        "Company Outlook", "Portfolio Signals", "Market Screener", "Market Banner", "Users", "Settings", "About",
    ]:
        assert f"<h3>{feature}</h3>" in help_dialog
    assert 'class="help-command" dir="ltr" data-i18n-skip' in help_dialog
    assert "app.admin_cli reset-password --username admin" in help_dialog
    assert '<h3>Using a phone or tablet</h3>' in help_dialog

    assert 'help: "Help"' in script
    assert 'help: "עזרה"' in script
    assert 'const defaultOpen = window.matchMedia("(min-width: 761px)").matches ? " open" : "";' in script
    assert 'data-modal="helpModal">${esc(t("help"))}</button>' in script
    assert 'if (id === "helpModal") requestAnimationFrame' in script

    assert '.help-directory {' in styles
    assert '.help-group > summary {' in styles
    assert '.help-group-content {' in styles
    assert '.help-group > summary:focus-visible {' in styles
    responsive = styles.split('@media (max-width: 760px) {', 1)[1]
    assert '.help-card {' in responsive
    assert 'max-height: calc(100dvh - 24px);' in responsive
    assert '.help-group-content,' in responsive
    assert 'grid-template-columns: 1fr;' in responsive
    assert '.nav-menu summary {' in responsive
    assert 'min-height: 44px;' in responsive
    assert '"Help": "עזרה"' in i18n
    assert '"Recommended setup order": "סדר הגדרה מומלץ"' in i18n
    assert '"Using a phone or tablet": "שימוש בטלפון או בטאבלט"' in i18n


def test_about_focuses_on_product_purpose_instead_of_runtime_details():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    api = (ROOT / "app/main.py").read_text()

    about_dialog = html.split('id="aboutModal"', 1)[1].split('id="helpModal"', 1)[0]
    load_about = script.split("async function loadAbout() {", 1)[1].split("function renderUsers()", 1)[0]
    about_endpoint = api.split('@app.get("/api/about")', 1)[1].split('@app.get("/api/portfolio")', 1)[0]

    assert 'class="modal-card about-card"' in about_dialog
    assert 'id="aboutContent" class="about-content" aria-live="polite"' in about_dialog
    assert 'class="about-product"' in load_about
    assert 'class="about-principles"' in load_about
    assert 'class="about-disclaimer" role="note"' in load_about
    assert "One financial picture" in load_about
    assert "Local control" in load_about
    assert '["Python"' not in load_about
    assert '["Local data"' not in load_about
    assert '["Backup"' not in load_about
    assert '"python"' not in about_endpoint
    assert '"features"' not in about_endpoint
    assert '.about-product {' in styles
    assert '.about-principles {' in styles


def test_security_chart_exposes_explainable_signal_and_accessible_zoom_controls():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert 'id="securityTechnicalSignal" class="technical-signal" role="status" aria-live="polite"' in html
    assert html.count('data-security-chart-zoom=') == 5
    assert 'id="securityChartZoomStatus"' in html
    assert 'id="securityChartZoomHelp" class="sr-only"' in html
    assert "function renderSecurityTechnicalSignal()" in script
    assert "technical_signals?.confirmed_breakout" in script
    assert "function securityChartZoomWindow(pointCount)" in script
    assert "function attachSecurityChartZoom(frame, allPoints, zoomWindow, dims)" in script
    assert 'hitbox.addEventListener("pointerdown"' in script
    assert 'svg.addEventListener("wheel"' in script
    assert 'svg.addEventListener("keydown"' in script
    assert 'event.key === "ArrowLeft"' in script
    assert '["Escape", "0", "Home"].includes(event.key)' in script
    assert "touch-action: pan-y" in styles
    assert '.chart-zoom-toolbar [data-security-chart-zoom="reset"]' in styles
    assert ".technical-signal-conditions" in styles


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
        "REST API &amp; MCP",
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
    assert settings.count('data-settings-section=') == 6
    assert settings.count('aria-controls="settingsPanel') == 6
    assert settings.count('aria-labelledby="settingsNav') == 6
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


def test_rest_and_mcp_access_settings_are_admin_only_clear_and_responsive():
    html = (ROOT / "web/index.html").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    settings = html.split('id="settingsModal"', 1)[1].split('id="backupScheduleModal"', 1)[0]
    assert 'id="settingsNavApi"' in settings
    assert 'data-settings-section="api"' in settings
    assert 'data-admin-only hidden' in settings
    assert 'id="settingsPanelApi"' in settings
    assert settings.count('name="apiAccessMode"') == 3
    assert 'name="apiAccessMode" value="disabled"' in settings
    assert 'name="apiAccessMode" value="read_only"' in settings
    assert 'name="apiAccessMode" value="read_write"' in settings
    assert settings.count('name="mcpAccessMode"') == 3
    assert 'name="mcpAccessMode" value="disabled"' in settings
    assert 'name="mcpAccessMode" value="read_only"' in settings
    assert 'name="mcpAccessMode" value="read_write"' in settings
    assert '<code dir="ltr">/api</code>' in settings
    assert '<code dir="ltr">/mcp/</code>' in settings
    assert 'POST /api/auth/token' in settings
    assert '&quot;service&quot;: &quot;rest&quot;' not in settings
    assert '"service": "rest"' in settings
    assert '"service": "mcp"' in settings
    assert 'Authorization: Bearer &lt;token&gt;' in settings
    assert 'id="apiAccessSummary"' in settings and 'aria-live="polite"' in settings
    assert 'id="mcpAccessSummary"' in settings and 'aria-live="polite"' in settings
    assert 'document.querySelectorAll("button[data-admin-only]")' in script
    assert 'api("/api/settings/integration-access"' in script
    assert 'JSON.stringify({ rest_mode: restMode, mcp_mode: mcpMode })' in script
    assert 'Turning a service off immediately revokes its active tokens. Continue?' in script
    assert 'state.mcpAccess = access.mcp' in script
    assert '.api-access-options {' in styles
    assert '.integration-access-services {' in styles
    assert '.api-access-option:has(input:checked)' in styles
    responsive = styles.split('@media (max-width: 760px) {', 1)[1]
    assert '.api-access-options {' in responsive
    assert '"REST API & MCP": "REST API ו־MCP"' in i18n
    assert '"MCP access mode": "מצב גישה ל־MCP"' in i18n
    assert '"Read only": "קריאה בלבד"' in i18n
    assert '"Read and write": "קריאה וכתיבה"' in i18n


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


def test_holdings_table_scrolls_with_sticky_headers_on_desktop():
    html = (ROOT / "web/index.html").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert 'class="table-wrap holdings-table-wrap" tabindex="0" role="region" aria-label="Scrollable holdings table"' in html
    desktop = styles.split("@media (min-width: 901px) {", 1)[1].split("@media", 1)[0]
    table_wrap = desktop.split(".holdings-table-wrap {", 1)[1].split("}", 1)[0]
    sticky_header = desktop.split(".holdings-table-wrap .holdings-table thead th {", 1)[1].split("}", 1)[0]
    assert "max-height: min(72dvh, 760px);" in table_wrap
    assert "overflow: auto;" in table_wrap
    assert "overscroll-behavior: contain;" in table_wrap
    assert "position: sticky;" in sticky_header
    assert "top: 0;" in sticky_header
    assert "z-index: 4;" in sticky_header


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


def test_dashboard_pension_comparison_is_bounded_scrollable_and_reconciles_results():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    bounded_table = styles.split(".long-term-savings-card .dashboard-projection-table {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in bounded_table
    assert "min-width: 0" in bounded_table
    assert "max-height: 220px" in bounded_table
    assert "overflow: auto" in bounded_table
    assert "scrollbar-gutter: stable" in bounded_table
    assert "<th>Starting Balance</th>" in script
    assert "<th>Net Deposits</th>" in script
    assert "<th>Investment Gain</th>" in script
    assert "result.starting_amount" in script
    assert "Projection only. Enter annual return after management fees" in html
    assert '"Starting Balance": "יתרה התחלתית"' in i18n
    assert '"Net Deposits": "הפקדות נטו"' in i18n
    assert '"Investment Gain": "רווח מהשקעות"' in i18n


def test_retirement_salary_schedule_allows_a_zero_income_period():
    script = (ROOT / "web/app.js").read_text()
    validation = script.split("function pensionPeriodFormValid() {", 1)[1].split("function pensionRateFormValid()", 1)[0]

    assert "hasContribution" not in validation
    assert "Number(toAge) > Number(fromAge)" in validation
    assert "survivorsFactor" in validation
    assert "Fill To Age and survivors factor when survivors coverage is selected" in script
    assert "Enter 0 for salary and deposits to model a period with no work or pension contributions." in (ROOT / "web/index.html").read_text()


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


def test_retirement_scenario_flow_uses_one_saved_list_and_create_edit_modal():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()

    assert 'aria-label="Retirement simulation flow"' not in html
    assert 'id="pensionScenarioEditor"' not in html
    assert 'id="pensionScenarioModal" class="modal" hidden' in html
    assert 'aria-labelledby="pensionScenarioFormTitle" aria-describedby="pensionScenarioModalIntro"' in html
    assert html.count('id="newPensionScenario"') == 1
    assert html.index('id="newPensionScenario"') < html.index('id="pensionScenarios"')
    assert 'id="newPensionScenario" type="button" title="Open a blank form.' in html
    assert "+ New scenario" in html
    assert 'id="pensionScenarioCount" class="retirement-scenario-count" role="status" aria-live="polite"' in html
    assert "Each saved scenario is one retirement alternative." in html
    assert 'class="retirement-scenario-card"' in script
    assert 'class="retirement-editing-badge"' not in script
    assert 'data-edit-pension-scenario="${index}"' in script
    assert 'data-schedule-pension-scenario="${index}"' in script
    assert 'data-delete-pension-scenario="${index}"' in script
    assert 'openModal("pensionScenarioModal", returnFocus' in script
    assert 'confirm(optionLabel("Remove this scenario?' in script
    assert "newPensionScenarioInline" not in html
    assert "newPensionScenarioInline" not in script
    assert "pensionProjectionSummary" not in html
    assert ".retirement-scenario-modal {" in styles
    assert ".retirement-scenario-list {\n  grid-template-columns: repeat(2, minmax(0, 1fr));" in styles
    mobile = styles.split('@media (max-width: 760px) {', 1)[1]
    assert ".retirement-scenario-list,\n  .retirement-period-fields," in mobile


def test_retirement_schedule_actions_follow_their_relevant_sections_and_explain_the_flow():
    html = (ROOT / "web/index.html").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()
    parser = _LabelParser()
    parser.feed(html)

    salary_section = html.split('aria-labelledby="salaryScheduleTitle"', 1)[1].split('</section>', 1)[0]
    return_section = html.split('aria-labelledby="returnScheduleTitle"', 1)[1].split('</section>', 1)[0]
    assert salary_section.index('id="pensionPeriodRows"') < salary_section.index('id="addPensionPeriod"')
    assert return_section.index('id="pensionRateRows"') < return_section.index('id="addPensionRate"')
    assert 'id="pensionStopWorkNow"' in salary_section
    assert 'id="showPensionPeriodEntry" type="button" aria-expanded="false" aria-controls="pensionPeriodEntry"' in salary_section
    assert 'id="pensionPeriodEntry" class="retirement-entry-card" hidden' in salary_section
    assert 'id="cancelPensionPeriodEntry"' in salary_section
    assert '>Save salary period</button>' in salary_section
    assert 'id="showPensionRateEntry" type="button" aria-expanded="false" aria-controls="pensionRateEntry"' in return_section
    assert 'id="pensionRateEntry" class="retirement-entry-card" hidden' in return_section
    assert 'id="cancelPensionRateEntry"' in return_section
    assert '>Save return period</button>' in return_section
    assert 'id="addPensionRate"' not in salary_section
    assert 'id="addPensionPeriod"' not in return_section
    assert html.count('class="ux-tooltip"') >= 8
    assert 'data-tooltip="Add a row for each age range' in html
    assert 'data-tooltip="Add at least one annual return assumption.' in html
    assert '"data-tooltip"' in i18n
    assert ".ux-tooltip:focus::after" in styles
    assert ".retirement-modal-footer" in styles
    schedule_controls = {
        "simPeriodFromMode", "simPeriodFrom", "simPeriodTo", "simPeriodIncome",
        "simPeriodContribution", "simPeriodDeposit", "simInsuranceTrack",
        "simDisabilityCoverage", "simSpouseSurvivorsCoverage",
        "simChildrenSurvivorsCoverage", "simSurvivorsFactor", "simRateFromMode",
        "simRateFrom", "simRateTo", "simRateAnnual",
    }
    assert schedule_controls <= parser.labeled_controls


def test_retirement_schedules_require_contiguous_salary_and_return_coverage():
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert "function pensionScheduleCoverageIssue(scenario, field, label)" in script
    assert 'pensionScheduleCoverageIssue(scenario, "income_periods", "Salary")' in script
    assert 'pensionScheduleCoverageIssue(scenario, "return_periods", "Return")' in script
    assert "schedule has overlapping periods at ages" in script
    assert "schedule is missing ages" in script
    assert "pensionScenarioScheduleIssue(scenario)" in script
    assert "runButton.disabled = !state.pensionScenarios.length || Boolean(scheduleProblem);" in script
    assert 'setPensionEntryVisibility("pensionPeriodEntry", "showPensionPeriodEntry", false' in script
    assert 'setPensionEntryVisibility("pensionRateEntry", "showPensionRateEntry", false' in script
    assert "schedule is missing ages" in i18n
    assert "schedule has overlapping periods" in i18n


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


def test_portfolio_reports_filter_complete_accounts_by_person_and_download_pdf():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    reports_dialog = html.split('id="reportsModal"', 1)[1].split('id="researchModal"', 1)[0]
    assert '<h2 id="reportsTitle">Portfolio reports</h2>' in reports_dialog
    assert 'id="reportPerson"' in reports_dialog
    assert 'All people' in reports_dialog
    assert 'id="reportAccountType"' in reports_dialog
    assert 'id="reportAccount"' in reports_dialog
    assert '<summary>More filters <small>Location and reporting period</small></summary>' in reports_dialog
    assert 'id="exportReportsPdf"' in reports_dialog
    assert '>Download PDF</button>' in reports_dialog

    assert "function reportAccountMatchesPrimaryFilters(account)" in script
    assert 'person_id: valueOf("reportPerson")' in script
    assert 'person_name: selectedReportPersonName()' in script
    assert 'api(`/api/local/reports?${params}`)' in script
    assert 'fetch(`/api/local/reports.pdf?${params}`)' in script
    assert 'await downloadResponse(response, `portfolio-report-${todayString()}.pdf`)' in script
    assert "window.print()" not in script
    assert 'class="report-account-card"' in script
    assert "No accounts match these filters" in script

    assert ".report-filter-panel {" in styles
    assert ".report-controls {" in styles
    assert ".report-account-card > summary:focus-visible" in styles
    assert ".report-holdings-table {" in styles
    assert '"All people": "כל האנשים"' in i18n
    assert '"Account category": "קטגוריית חשבון"' in i18n
    assert '"Download PDF": "הורדת PDF"' in i18n


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


def test_authentication_blocks_the_dashboard_until_a_session_is_verified():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    parser = _LabelParser()
    parser.feed(html)

    assert '<div id="authOverlay" class="auth-overlay">' in html
    assert '<div id="appShell" class="app-shell" inert aria-hidden="true">' in html
    assert {"loginUsername", "loginPassword", "currentPassword", "newPassword", "confirmPassword"} <= parser.labeled_controls
    assert 'autocomplete="username"' in html
    assert 'autocomplete="current-password"' in html
    assert html.count('autocomplete="new-password"') >= 3
    assert html.count('minlength="8" maxlength="256"') == 3
    assert 'Passwords are salted and hashed, never stored in readable form.' in html
    assert 'Sign in to open the shared portfolio dashboard.' not in html
    assert 'First sign-in: use admin / admin, then choose a new password.' not in html
    assert 'async function restoreAuthSession()' in script
    assert 'if (await restoreAuthSession()) await startAuthenticatedApp();' in script
    assert 'headers["X-CSRF-Token"] = state.auth.csrfToken' in script
    assert 'shell.inert = Boolean(locked)' in script


def test_role_aware_user_management_is_accessible_and_responsive():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert 'id="currentUserName" class="current-user-name" dir="auto"' in html
    assert 'id="readOnlyNotice" class="info-strip read-only-notice" role="status" hidden' in html
    assert 'id="usersModal" class="modal" hidden' in html
    assert 'role="dialog" aria-modal="true" aria-labelledby="usersTitle"' in html
    assert all(role in html for role in ('value="Admin"', 'value="Operator"', 'value="Viewer"'))
    assert '${canAdmin() ? `<button class="nav-item" type="button" data-modal="usersModal">' in script
    assert 'return ["Admin", "Operator"].includes(currentUser()?.role)' in script
    assert 'const readOnly = currentUser()?.role === "Viewer"' in script
    assert 'button.setAttribute("aria-disabled", "true")' in script
    assert '.users-layout {' in styles
    mobile = styles.split('@media (max-width: 760px) {', 1)[1]
    assert '.auth-actions,\n  .users-layout,\n  .user-form,\n  .user-management-item {' in mobile
    assert '.auth-panel input,\n  .auth-panel select,\n  .auth-panel button,' in mobile
    assert 'min-height: 44px;' in mobile
    assert '"Viewer access is read-only": "לצופה יש גישה לקריאה בלבד"' in i18n


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
