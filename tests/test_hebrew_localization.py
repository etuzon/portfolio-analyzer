from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_alert_progress_and_run_history_follow_active_language():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("t", "locale", "fmt", "alertRunStatusText", "alertRunProgressText", "renderAlerts", "alertRunIsActive", "scheduleAlertRefresh"):
        start = source.index(f"function {name}(")
        end = source.index("\nfunction ", start + 1)
        functions.append(source[start:end])
    translations = source[source.index("const TRANSLATIONS ="):source.index("function locale(")]
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text() + translations
    script += "\n".join(functions) + """
      const state = {language: 'he', alertConditions: [1]};
      window.setTimeout = () => 1;
      const nodes = {};
      const $ = (id) => nodes[id] ||= {};
      const esc = (text) => String(text);
      const formatDateTime = () => '29/10/2026, 21:47';
      const renderAlertConditions = () => {};
      const phases = ['starting', 'loading_saved_data', 'loading_rule_data', 'evaluating', 'unknown'];
      const output = [];
      for (const language of ['he', 'en', 'he']) {
        state.language = language;
        renderAlerts({rules: [], active_signals: [], runs: [{
          status: 'running', progress: {phase: 'loading_rule_data', completed: 20, total: 27}
        }]});
        output.push({
          progress: phases.map((phase) => alertRunProgressText({phase, completed: 20, total: 27})),
          withoutTotal: alertRunProgressText({phase: 'starting'}),
          history: nodes.alertRunHistory.innerHTML,
          legacyKey: t('appName')
        });
      }
      process.stdout.write(JSON.stringify(output));
    """
    result = subprocess.run(["node"], input=script, check=True, capture_output=True, text=True)
    hebrew, english, switched_back = json.loads(result.stdout)

    assert hebrew["progress"] == [
        "מתחיל… 20/27", "טוען את נתוני התיק השמורים… 20/27",
        "טוען נתונים לכלל… 20/27", "מחשב את תוצאת הכלל… 20/27", "רץ… 20/27",
    ]
    assert hebrew["withoutTotal"] == "מתחיל…"
    assert "טוען נתונים לכלל… 20/27" in hebrew["history"]
    assert "מניות שנבדקו" in hebrew["history"]
    assert not re.search(r">[^<]*[A-Za-z][^<]*<", hebrew["history"])
    assert english["progress"] == [
        "Starting… 20/27", "Loading saved portfolio data… 20/27",
        "Loading rule data… 20/27", "Evaluating rule… 20/27", "Running… 20/27",
    ]
    assert "Loading rule data… 20/27" in english["history"]
    assert "stocks checked" in english["history"]
    assert not re.search(r"[א-ת]", english["history"])
    assert hebrew == switched_back
    assert hebrew["legacyKey"] != "appName"
    assert english["legacyKey"] != "appName"


def test_company_outlook_localizes_mermaid_labels_missing_data_and_report_copy():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("t", "companyOutlookDiagramSource", "renderCompanyOutlook", "renderCompanyOutlookDiagramFallback"):
        start = source.index(f"function {name}(")
        end = re.search(r"\n(?:async )?function ", source[start + 1:])
        functions.append(source[start:start + 1 + end.start()])
    translations = source[source.index("const TRANSLATIONS ="):source.index("function locale(")]
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text() + translations
    script += "\n".join(functions) + """
      const assert = require('node:assert/strict');
      const state = {language: 'he'};
      const nodes = {};
      const $ = (id) => nodes[id] ||= {};
      const esc = (text) => String(text);
      const fmt = (value) => String(value ?? '∅');
      const pct = (value) => `${value}%`;
      const formatDate = () => '31/12/2025';
      let diagramSource;
      const renderCompanyOutlookDiagram = (outlook) => {diagramSource = companyOutlookDiagramSource(outlook.mermaid);};
      const outlook = {symbol: 'BRKR', score: 9, rank: 1, label: 'Weak', confidence: 'Low',
        peer_source: 'No peer source available', industry: {health: 'Not available', score: 0},
        simple_words: 'BRKR scores 9/100. It ranks 1 out of 1 companies using available annual report numbers. The Laboratory Analytical Instruments outlook looks not available. Cash-flow and balance-sheet measures are included when filed; missing statement evidence lowers confidence. Confidence: Low.',
        missing: ['same-industry peer reports', 'related-industry reports'],
        companies: [{symbol: 'BRKR', name: 'BRUKER CORP', industry: 'Laboratory Analytical Instruments'}],
        graph: {nodes: [{id: 'industry', label: 'Unclassified industry'}], edges: []},
        mermaid: 'flowchart LR\\n T["BRKR<br/>Revenue growth: 2.1%<br/>Net margin: -0.3%<br/>Score: 9"] -->|"competes in"| I["Unclassified industry<br/>Median revenue growth: n/a<br/>Health: Pressure"]'
      };
      renderCompanyOutlook(outlook);
      assert.ok(diagramSource.includes('שיעור רווח נקי: -0.3%'));
      assert.ok(diagramSource.includes('פועלת בענף'));
      assert.ok(diagramSource.includes('חציון צמיחת ההכנסות: לא זמין'));
      assert.ok(!diagramSource.includes('Pressure'));
      assert.ok(nodes.companyOutlookTable.innerHTML.includes('<th>שיעור רווח נקי</th>'));
      assert.ok(nodes.companyOutlookWords.innerHTML.includes('דוחות של מתחרות מאותו ענף'));
      assert.ok(!/[A-Za-z]/u.test(nodes.companyOutlookWords.innerHTML.replace(/<[^>]+>/gu, '').replaceAll('BRKR', '')));
      assert.ok(!/[A-Za-z]/u.test(nodes.companyOutlookStatus.textContent.replaceAll('BRKR', '')));
      assert.ok(renderCompanyOutlookDiagramFallback(outlook).includes('ענף שלא סווג'));
      state.language = 'en';
      renderCompanyOutlook(outlook);
      assert.equal(diagramSource, outlook.mermaid);
      for (const id of ['companyOutlookTable', 'companyOutlookWords', 'companyOutlookSummary']) {
        assert.ok(!/[א-ת]/u.test(nodes[id].innerHTML));
      }
      for (const language of ['he', 'en']) {
        state.language = language;
        renderCompanyOutlook({...outlook, score: 43, score_components: {company_fundamentals: 16}, companies: [
          {symbol: 'BRKR', score: 16, industry: 'Computer Communications Equipment'},
          {symbol: 'PEER', score: 33, industry: 'Computer Communications Equipment'},
        ]});
        const table = nodes.companyOutlookTable.innerHTML;
        assert.ok(table.includes('16/45') && table.includes('33/45'));
        assert.ok(!table.includes('/32') && !table.includes('/100'));
        assert.ok(nodes.companyOutlookSummary.innerHTML.includes('43/100'));
        assert.ok(table.includes(language === 'he' ? 'מדדי החברה' : 'Company signals'));
        assert.ok(table.includes(language === 'he' ? 'מתוך 45' : 'out of 45'));
        if (language === 'he') assert.ok(!table.includes('Computer Communications Equipment'));
      }
    """
    subprocess.run(["node"], input=script, check=True, capture_output=True, text=True)


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


def test_finance_report_localizes_summary_source_and_mobile_labels():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("renderFinanceReport", "providerStatusHint", "financeReportMetricTooltip"):
        start = source.index(f"function {name}(")
        end = re.search(r"\n(?:async )?function ", source[start + 1:])
        functions.append(source[start:start + 1 + end.start()])
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text() + "\n".join(functions) + """
      const assert = require('node:assert/strict');
      const state = {language: 'he'};
      const nodes = {};
      const $ = (id) => nodes[id] ||= {};
      const t = (text) => window.PortfolioI18n.translate(text, state.language);
      const esc = (text) => String(text);
      const fmt = (value) => String(value ?? '∅');
      const pct = (value) => `${value ?? '∅'}%`;
      const formatDate = (value) => value ? value.split('-').reverse().join('/') : '—';
      const providerDisplayName = () => 'SEC';
      const report = {symbol: 'CSCO', profile: {name: 'CISCO SYSTEMS, INC.'},
        summary: {years: 6, latest_revenue: 56654000000, latest_long_term_debt: 1750000000},
        reports: [{fiscal_date: '2026-07-31', revenue: 56654000000}],
        provider_status: {sec_company_facts: 'ok'}};
      for (const language of ['he', 'en', 'he']) {
        state.language = language;
        renderFinanceReport(report);
        const summary = nodes.financeReportSummary.innerHTML;
        const table = nodes.financeReportTable.innerHTML;
        assert.ok(summary.includes('56654000000'));
        assert.ok(table.includes('31/07/2026'));
        if (language === 'he') {
          assert.ok(summary.includes('שנות דיווח'));
          assert.ok(summary.includes('הכנסות בדוח האחרון'));
          assert.ok(summary.includes('חוב לטווח ארוך'));
          assert.ok(!/[A-Za-z]/u.test(summary.replace(/<[^>]+>/gu, '')));
          assert.ok(!/[A-Za-z]/u.test(table.replace(/<[^>]+>/gu, '')));
          assert.ok(table.includes('data-label="הכנסות"'));
          assert.equal(nodes.financeReportStatus.textContent, 'CISCO SYSTEMS, INC. · נתונים מאת SEC');
        } else {
          assert.ok(summary.includes('Years') && summary.includes('Latest revenue'));
          assert.ok(!/[א-ת]/u.test(summary + table + nodes.financeReportStatus.textContent));
        }
      }
      renderFinanceReport({...report, reports: [], provider_status: {}});
      assert.ok(nodes.financeReportTable.innerHTML.includes('לא נמצאו דוחות כספיים שנתיים'));
      assert.ok(nodes.financeReportStatus.textContent.includes('הנתונים המקוונים נטענו'));
      for (const status of ['stale', 'missing API key', 'error', 'missing']) {
        renderFinanceReport({...report, provider_status: {sec_company_facts: status}});
        assert.ok(!/[A-Za-z]/u.test(nodes.financeReportStatus.textContent.replace(report.profile.name, '').replaceAll('SEC', '')));
      }
      const growth = {fiscal_date: '2025-07-26', comparison_fiscal_date: '2024-07-27', previous_net_income: 10320, net_income: 10180};
      let tooltip = financeReportMetricTooltip('Net income growth', growth, {fiscal_date: '2020-01-01'});
      assert.ok(tooltip.includes('26/07/2025') && tooltip.includes('27/07/2024'));
      assert.ok(!tooltip.includes('2020'));
      assert.ok(tooltip.includes('10320') && tooltip.includes('10180'));
      assert.ok(tooltip.includes('נוסחה:'));
      assert.ok(!/[A-Za-z]/u.test(tooltip));
      assert.ok(financeReportMetricTooltip('Net income growth', {fiscal_date: '2024-07-27'}).includes('אין דוח שנתי מוקדם יותר'));
      assert.ok(financeReportMetricTooltip('Net income growth', {...growth, previous_net_income: 0}).includes('הסכום הקודם הוא אפס'));
      renderFinanceReport({...report, reports: [growth]});
      assert.ok(nodes.financeReportTable.innerHTML.includes('title="השינוי ברווח הנקי השנתי'));
      assert.ok(nodes.financeReportTable.innerHTML.includes('27/07/2024'));
      state.language = 'en';
      tooltip = financeReportMetricTooltip('Net income growth', growth);
      assert.ok(tooltip.includes('26/07/2025') && tooltip.includes('27/07/2024'));
      assert.ok(tooltip.includes('previous available annual report'));
      assert.ok(!/[א-ת]/u.test(tooltip));
    """
    subprocess.run(["node"], input=script, check=True, capture_output=True, text=True)


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
    assert "border-bottom: 1px solid #24262b" in styles
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
