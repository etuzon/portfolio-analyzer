from html.parser import HTMLParser
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


class _VisibleEnglishParser(HTMLParser):
    translated_attributes = {"placeholder", "aria-label", "title", "alt"}

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.values = set()

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_depth += 1
        for name, value in attrs:
            if name in self.translated_attributes and value and re.search(r"[A-Za-z]", value):
                self.values.add(value.strip())

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
        value = " ".join(data.split())
        if value and re.search(r"[A-Za-z]", value):
            self.values.add(value)


TECHNICAL_UI_VALUES = {
    "1M", "6M", "1Y", "3Y", "5Y",
    "MA 7", "MA 10", "MA 15", "MA 30",
    "AMEX", "NASDAQ", "NYSE", "TASE", "US", "RSU",
    "ANET, HPE, JNPR", "AVGO, MSFT", "NASDAQ, NYSE, TASE…",
    "USD/ILS, IXIC, GCUSD", "Asia/Jerusalem", "dd/mm/yyyy",
}


def test_hebrew_is_the_default_document_language_and_direction():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert '<html lang="he" dir="rtl" class="i18n-pending">' in html
    assert html.index('/i18n.js?v=1.2.7') < html.index('/app.js?v=0.9.8')
    assert 'language: "he"' in script
    assert 'state.language = saved === "en" ? "en" : "he"' in script
    assert 'window.PortfolioI18n?.applyToDocument(state.language)' in script


def test_initial_page_stays_blank_and_white_until_localization_is_ready():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert 'id="localization-boot-style"' in html
    assert "html.i18n-pending body" in html
    assert "background: #fff" in html
    assert "visibility: hidden" in html
    assert 'function revealInitializedApp()' in script
    assert 'loadClientStateFromStorage();\n  revealInitializedApp();' in script
    assert 'initializeApp().catch(reportBackgroundError).finally(revealInitializedApp);' in script


def test_localization_runtime_handles_dynamic_text_and_attributes():
    i18n = (ROOT / "web/i18n.js").read_text()

    assert '"Portfolio Analyzer": "מנהל תיק השקעות"' in i18n
    assert '"Employee Stock Options": "אופציות לעובדים"' in i18n
    assert '"placeholder", "aria-label", "title", "alt"' in i18n
    assert "new MutationObserver" in i18n
    assert "withOuterWhitespace(source, formatter(...match))" in i18n
    assert "source.replace(key" not in i18n
    assert 'field.setAttribute("dir", "auto")' in i18n
    assert 'field.setAttribute("dir", "ltr")' in i18n


def test_donut_charts_localize_composed_titles_captions_and_legend_labels():
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert "const localizedTitle = optionLabel(title)" in script
    assert ".filter(Boolean).map(groupLabel)" in script
    assert 'extraClass === "currency-allocation-card" && label !== "Unknown"' in script
    assert "currencyDisplayLabel(label) : optionLabel(label)" in script
    assert '["נכס", "מוביל"]' in script
    assert '"Asset mix": "הרכב הנכסים"' in i18n


def test_data_gap_badges_and_provider_names_use_localized_display_labels():
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert "const localizedMissing = item.missing.map(optionLabel)" in script
    assert 'local_portfolio: "Local portfolio"' in script
    assert "optionLabel(names[key] || cleanSourceLabel(value))" in script
    assert '"income": "הכנסות"' in i18n
    assert '"Import DB": "מסד הייבוא"' in i18n


def test_populated_dashboard_values_are_localized_at_composition_time():
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert 'return { ...band, label: optionLabel(band.label) }' in script
    assert 'const drivers = (risk.drivers || []).slice(0, 4).map(simpleDriver).map(optionLabel)' in script
    assert '? `${optionLabel("Risk")} ${band.label} · ${risk.score}/100`' in script
    assert 'optionLabel("Main reasons:")' in script
    assert 'optionLabel("Components:")' in script
    assert 'optionLabel("Total portfolio risk")' in script
    assert 'optionLabel("Industry risk")' in script
    assert 'optionLabel("No single factor stands out")' in script
    assert 'const missingField = text.slice(8).trim()' in script
    assert '`היעדר נתוני ${optionLabel(missingField)} מקטין את ודאות האומדן`' in script
    assert '.map((group) => ({ ...group, label: optionLabel(group.label)' in script
    assert 'optionLabel("Holding Profit")' in script
    assert 'optionLabel("Total P/L")' in script
    assert 'optionLabel("units")' in script
    assert 'optionLabel(isImportedAccount(account) ? "Imported" : "Manual")' in script
    assert '"Investment risk formula": "נוסחת סיכון ההשקעות"' in i18n
    assert '"Total portfolio risk": "סיכון כולל בתיק"' in i18n
    assert '"Industry risk": "סיכון ענפי"' in i18n
    assert '"Elevated": "מוגבר"' in i18n
    assert '"Price swings could cause meaningful losses.": "תנודות מחירים עלולות לגרום להפסדים משמעותיים."' in i18n
    assert '"Main reasons:": "הסיבות העיקריות:"' in i18n
    assert 'אופק ההשקעה הוא ${value} שנים' in i18n
    assert 'ההחזקה הבודדת הגדולה ביותר מהווה ${value} מהשווי הכולל, כולל מזומן' in i18n
    assert 'לאחר איחוד כל ההחזקות באותו נייר ערך, הוא מהווה ${value} משווי ניירות הערך בלבד, ללא מזומן' in i18n
    assert '"Financial Services": "שירותים פיננסיים"' in i18n


def test_provider_industry_labels_have_shared_hebrew_translations():
    i18n = (ROOT / "web/i18n.js").read_text()

    translations = {
        "Marine Transportation": "תובלה ימית",
        "Major Banks": "בנקים גדולים",
        "Real Estate Investment Trusts": "קרנות השקעה בנדל״ן (ריט)",
        "Oil & Gas Production": "הפקת נפט וגז",
        "Apparel": "הלבשה",
        "Finance/Investors Services": "פיננסים / שירותים למשקיעים",
        "Diversified Financial Services": "שירותים פיננסיים מגוונים",
        "Life Insurance": "ביטוח חיים",
        "Investment Managers": "מנהלי השקעות",
        "Biotechnology: Laboratory Analytical Instruments": "ביוטכנולוגיה: מכשור אנליטי למעבדות",
        "EDP Services": "שירותי עיבוד נתונים (EDP)",
        "Finance: Consumer Services": "פיננסים: שירותים לצרכן",
    }
    for english, hebrew in translations.items():
        assert f'"{english}": "{hebrew}"' in i18n


def test_security_detail_kpi_headers_are_localized_in_hebrew():
    script = (ROOT / "web/app.js").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()

    assert '<span>${esc(optionLabel(label))}</span>' in script
    assert '"Data provider": "ספק נתונים"' in i18n
    assert '"Cost basis": "בסיס עלות"' in i18n
    assert '"Average buy price": "מחיר קנייה ממוצע"' in i18n
    assert '"Holding profit (open)": "רווח מהחזקה (לא ממומש)"' in i18n
    assert '"Closed profit": "רווח ממומש"' in i18n


def test_rtl_layout_uses_semantic_direction_and_logical_properties():
    styles = (ROOT / "web/styles.css").read_text()

    assert 'html[dir="rtl"] .app-shell' in styles
    assert 'font-family: "Noto Sans Hebrew", Inter' in styles
    assert "border-inline-end: 1px solid #24262b" in styles
    assert "margin-inline-start: auto" in styles
    assert "padding-inline-start: 22px" in styles
    assert "inset-inline-start: 8px" in styles


def test_every_static_english_label_is_translated_or_intentionally_technical():
    html = (ROOT / "web/index.html").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()
    parser = _VisibleEnglishParser()
    parser.feed(html)
    encoded_keys = re.findall(r'^\s+"((?:[^"\\]|\\.)+)":', i18n, re.MULTILINE)
    translation_keys = {json.loads(f'"{key}"') for key in encoded_keys}

    uncovered = parser.values - translation_keys - TECHNICAL_UI_VALUES

    assert uncovered == set()
