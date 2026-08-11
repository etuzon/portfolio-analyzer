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


def test_employee_option_grants_use_all_countries_and_three_supported_currencies():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert 'id="manualSecurityLocation" autocomplete="country-name" required aria-required="true"' in html
    assert 'id="manualSecurityLocation" list="countryOptions"' not in html
    assert 'id="manualSecurityCurrency" required aria-required="true"' in html
    assert 'const EMPLOYEE_OPTION_CURRENCIES = ["ILS", "USD", "EUR"]' in script
    assert "function companyCountryChoices()" in script
    assert "return REGION_CODES.map((code)" in script
    assert '.forEach((id) => setCurrencyOptions(id));' in script
    assert 'setCurrencyOptions("manualSecurityCurrency", isEmployeeOption ? EMPLOYEE_OPTION_CURRENCIES : null)' in script
    assert "Employee stock-option currency must be ILS, USD, or EUR." in script


def test_employee_option_workflow_filters_to_esop_accounts_and_employee_grants():
    script = (ROOT / "web/app.js").read_text()

    assert 'String(account.type || "").toUpperCase() === "ESOP"' in script
    assert 'item.instrument_type === "EMPLOYEE_STOCK_OPTION"' in script
    assert 'tx.instrument_type === "EMPLOYEE_STOCK_OPTION"' in script
    assert "setEmployeeOptionGuideStep(2)" in script


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
