"""Language coverage for static UI, provider classifications and composed metadata."""
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_js(body):
    script = 'const window = {};\n' + (ROOT / 'web/i18n.js').read_text() + '\n' + body
    completed = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def test_provider_industries_are_localized_without_changing_unknown_classification_meaning():
    catalog = next(ast.literal_eval(node.value) for node in ast.parse((ROOT / 'app/main.py').read_text()).body
                   if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'INDUSTRY_CATALOG' for t in node.targets))
    run_js('const catalog = ' + json.dumps(catalog) + r''';
const assert = require('node:assert/strict');
const i18n = window.PortfolioI18n;
const examples = {
 'Deep Sea Foreign Transportation of Freight': 'תובלה ימית בינלאומית של מטענים',
 'Apparel & Other Finished Prods of Fabrics & Similar Matl': 'הלבשה ומוצרים מוגמרים מבדים ומחומרים דומים',
 'National Commercial Banks': 'בנקים מסחריים לאומיים',
 'State Commercial Banks': 'בנקים מסחריים ברישוי מדינתי',
 'Water Transportation': 'תחבורה ימית',
 'Services-Computer Programming Services': 'שירותי תכנות מחשבים'
};
for (const [label, expected] of Object.entries(examples)) {
 assert.equal(i18n.industry(label, 'he'), expected);
 assert.equal(i18n.translate(label, 'he'), expected);
 assert.equal(i18n.industry(label, 'en'), label);
 assert.equal(i18n.industry(label.toLowerCase(), 'he'), expected);
}
for (const label of catalog) {
 assert.notEqual(i18n.industry(label, 'he'), 'שם הענף מהספק אינו זמין בעברית', label);
 assert.match(i18n.industry(label, 'he'), /[א-ת]/u, label);
 assert.equal(i18n.industry(label, 'en'), label);
}
assert.equal(i18n.industry('Aerospace and Defense', 'he'), 'תעופה, חלל וביטחון');
assert.equal(i18n.industry('REIT—Mortgage', 'he'), 'קרנות השקעה בנדל״ן למשכנתאות');
assert.equal(i18n.industry('Unseen provider SIC label', 'he'), 'שם הענף מהספק אינו זמין בעברית');
assert.equal(i18n.industry('Unseen provider SIC label', 'en'), 'Unseen provider SIC label');
assert.equal(i18n.industry('ענף ידני', 'he'), 'ענף ידני');
assert.equal(i18n.translate('Acme Company NASDAQ', 'he'), 'Acme Company NASDAQ');
''')


def test_composed_instrument_metadata_and_nested_error_are_translated_with_values_intact():
    run_js(r'''
const assert = require('node:assert/strict');
const t = value => window.PortfolioI18n.translate(value, 'he');
const source = 'BOND · Grant ID 5827 · Grant Date 14/05/2026 · Vesting Start 02/03/2026 · Underlying BRKR · Exp 14/05/2034 · Strike 45.46 · Multiplier 1 · Imported source profile';
const result = t(source);
for (const word of ['Grant', 'Vesting', 'Underlying', 'Exp', 'Strike', 'Multiplier', 'Imported']) assert.ok(!result.includes(word), word);
for (const value of ['5827', '14/05/2026', '02/03/2026', 'BRKR', '14/05/2034', '45.46']) assert.ok(result.includes(value), value);
assert.equal(t('Grant 5827 · Granted 14/05/2026 · Expires 14/05/2034'), 'מענק 5827 · הוענק 14/05/2026 · פוקע 14/05/2034');
assert.equal(t('Company Ltd · BOND · Multiplier 1'), 'Company Ltd · אג"ח · מכפיל 1');
assert.equal(t('Error: Security currency must be ILS, USD, or EUR.'), 'שגיאה: מטבע נייר הערך חייב להיות שקל, דולר או אירו.');
assert.equal(t('Cash: ₪ 100\nLocal value: USD 26'), 'מזומן: ₪ 100\nשווי מקומי: USD 26');
assert.equal(window.PortfolioI18n.translate(source, 'en'), source);
''')


def test_industry_rendering_keeps_raw_groups_separate_and_localizes_display_only():
    source = (ROOT / 'web/app.js').read_text()
    functions = []
    for name in ('industryDisplayLabel', 'industryHoldingsBySecurity', 'industryHoldingHtml', 'renderIndustrySplit'):
        start = source.index(f'function {name}(')
        end = re.search(r'^}', source[start:], re.M).end()
        functions.append(source[start:start + end])
    run_js('\n'.join(functions) + r'''
const assert = require('node:assert/strict');
const state = {language:'he',baseCurrency:'ILS',riskSnapshot:{total:{score:20}}};
const optionLabel = value => window.PortfolioI18n.translate(value,state.language);
const currencyDisplayLabel = value => value;
const industryLabel = item => item.industry;
const normalizedField = item => item.holding.market_value;
const holdingMarketKey = h => h.stock_market;
const sum = values => values.reduce((a,b) => a+b,0);
const portfolioAccounts = () => [];
const accountRiskCashValue = () => 0;
const accountHorizonYears = () => null;
const riskScoreForItems = () => ({score:20});
const riskBadge = () => '';
const fmt = value => String(value);
const money = value => '₪ '+value;
const colorAt = () => '#abc';
const esc = text => String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const sourceItems=['National Commercial Banks','Unseen provider one','Unseen provider two'].map((industry,index)=>({industry,holding:{symbol:'T'+index,stock_market:'NYSE',asset_class:'EQUITY',market_value:100}}));
const before=JSON.stringify(sourceItems);
const result=renderIndustrySplit(sourceItems);
assert.ok(result.includes('בנקים מסחריים לאומיים'));
assert.ok(!result.includes('National Commercial Banks'));
assert.equal((result.match(/class="industry-split-row"/g)||[]).length,3);
assert.equal((result.match(/<b>שם הענף מהספק אינו זמין בעברית<\/b>/g)||[]).length,2);
assert.equal(JSON.stringify(sourceItems),before);
state.language='en';
const english=renderIndustrySplit(sourceItems);
assert.ok(english.includes('National Commercial Banks'));
assert.ok(english.includes('Unseen provider one'));
assert.ok(!/[א-ת]/u.test(english));
''')


class InterfaceCopy(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.items = set()

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'code'):
            self.skip += 1
        if not self.skip:
            for key, value in attrs:
                if key in ('title', 'aria-label', 'placeholder', 'data-label') and value:
                    self.items.add(value)

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'code'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, text):
        text = ' '.join(text.split())
        if not self.skip and re.search('[A-Za-z]{3}', text):
            self.items.add(text)


def test_static_interface_and_help_copy_have_hebrew_translations():
    parser = InterfaceCopy()
    parser.feed((ROOT / 'web/index.html').read_text())
    # Data identifiers, market codes, language name and literal input examples.
    unchanged = {'0', '0.00', '100', 'AMEX', 'ANET, HPE, JNPR', 'AVGO, MSFT', 'Asia/Jerusalem',
                 'English', 'NASDAQ', 'NASDAQ, NYSE, TASE…', 'NYSE', 'REST API', 'RSU', 'TASE',
                 'US', 'IL', 'USD/ILS, IXIC, GCUSD', 'dd/mm/yyyy'}
    output = run_js('const copy = ' + json.dumps(sorted(parser.items)) + ';\n'
                    'console.log(JSON.stringify(copy.filter(text => window.PortfolioI18n.translate(text,"he") === text)));')
    missing = set(json.loads(output)) - unchanged
    assert not missing, 'Missing Hebrew interface/Help translations: ' + repr(sorted(missing))
