"""Behavior checks for report currency integrity, history and preview recovery."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'web/app.js').read_text()


def functions(*names):
    result = []
    for name in names:
        start = re.search(rf'^(?:async )?function {name}\(', SOURCE, re.M).start()
        end = re.search(r'^}', SOURCE[start:], re.M).end()
        result.append(SOURCE[start:start + end])
    return '\n'.join(result)


def run(script):
    subprocess.run(['node'], input=script, check=True, capture_output=True, text=True)


BASE = """
const assert = require('node:assert/strict');
const nodes = {};
const $ = id => nodes[id] ||= {innerHTML:'',textContent:'',value:'',setAttribute(){},removeAttribute(){}};
const state = {baseCurrency:'ILS',language:'en',fxRates:{'USD/ILS':3,'EUR/ILS':4},localAccounts:[],activeReportFilters:{}};
const sum = values => values.reduce((a,b)=>a+b,0);
const t = text => text;
const esc = value => String(value ?? '').replaceAll('<','&lt;').replaceAll('>','&gt;');
const money = (value,currency) => `${currency}:${value}`;
const fmt = value => String(value);
const pct = value => `${value}%`;
const compactMoney = money;
const accountLabel = account => account.label;
const cleanSourceLabel = value => value;
const personLabel = person => person.name;
const optionLabel = value => value;
const countryDisplayLabel = value => value;
const currencyDisplayLabel = value => value;
const colorAt = index => ['blue','green'][index % 2];
const formatDate = date => date.split('-').reverse().join('/');
"""
MONEY_FUNCTIONS = functions('reportAmount', 'reportSum', 'reportMoney', 'reportAccountAmounts')


def test_report_converts_each_position_before_aggregation_and_requires_fx():
    run(BASE + MONEY_FUNCTIONS + """
const account={cash:100,currency:'EUR',holdings:[{market_value:200,profit:10,currency:'USD'}]};
assert.deepEqual(reportAccountAmounts(account), {cash:400,securities:600,profit:30,value:1000});
assert.deepEqual(reportAccountAmounts(account,'EUR'), {cash:100,securities:150,profit:7.5,value:250});
assert.equal(reportAmount(10,'ILS','USD'),10/3);
assert.equal(reportAmount(10,'GBP'),null);
assert.equal(reportAmount(0,'GBP'),0);
assert.equal(reportAmount(null,'USD'),null);
assert.equal(reportSum([5,null]),null);
assert.equal(reportMoney(null),'Not available');
delete state.fxRates['USD/ILS'];
assert.equal(reportAccountAmounts(account).value,null);
assert.equal(reportAccountAmounts(account,'EUR').value,null);
""")


def test_retirement_records_are_separate_from_cash_and_securities_totals():
    run(BASE + MONEY_FUNCTIONS + functions('renderReportSummary','renderReportScopeSummary') + r"""
const account={id:'one',label:'Investments <test>',currency:'USD',type:'Investment',location:'USA',cash:100,
  holdings:[{symbol:'ABC',market_value:200,profit:10,currency:'USD'}],
  funds:[{kind:'Pension',amount:200000,monthly_estimate:1000}]};
renderReportSummary({accounts:1,holdings:1,funds:{count:1},account_details:[account]});
assert.match($('reportsSummary').innerHTML,/ILS:900/);
assert.match($('reportsSummary').innerHTML,/P\/L on open positions/);
assert.doesNotMatch($('reportsSummary').innerHTML,/600000/);
assert.match($('reportRetirementSummary').innerHTML,/ILS:600000/);
assert.match($('reportsDetails').innerHTML,/Investments &lt;test&gt;/);
assert.match($('reportsDetails').innerHTML,/USD:300/);
delete state.fxRates['USD/ILS'];
renderReportSummary({accounts:1,holdings:1,account_details:[account]});
assert.match($('reportValuationNote').textContent,/exchange rate or amount is missing/);
assert.match($('reportsSummary').innerHTML,/Not available/);
assert.doesNotMatch($('reportsByType').innerHTML,/100%/);
""")


def test_history_uses_elapsed_dates_and_preserves_account_colors_across_measures():
    run(BASE + MONEY_FUNCTIONS + functions('renderAccountTrend') + r"""
const trend={accounts:[{account:{label:'One',currency:'ILS'},points:[
  {date:'2026-10-01',value:100,profit_percent:0},
  {date:'2026-10-02',value:105,profit_percent:5},
  {date:'2026-10-11',value:110,profit_percent:10}]}]};
renderAccountTrend(trend);
let chart=$('accountTrendChart').innerHTML;
assert.match(chart,/M 100 40.545[^L]*L 178 /); // one day is 1/10 of the plot width
assert.match(chart,/01\/10\/2026/);
assert.match(chart,/11\/10\/2026/);
assert.match(chart,/stroke="blue"/);
assert.doesNotMatch(chart,/NaN|Infinity/);
state.reportTrendMetric='profit_percent';
renderAccountTrend(trend);
assert.match($('accountTrendChart').innerHTML,/stroke="blue"/);
assert.match($('accountTrendChart').innerHTML,/not a period return/);
trend.accounts[0].points=trend.accounts[0].points.slice(0,1);
renderAccountTrend(trend);
assert.match($('accountTrendChart').innerHTML,/<circle/);
assert.doesNotMatch($('accountTrendChart').innerHTML,/NaN|Infinity/);
state.reportTrendMetric='value';
trend.accounts[0].account.currency='GBP';
renderAccountTrend(trend);
assert.match($('accountTrendChart').innerHTML,/No chart values available/);
trend.accounts.push({account:{label:'Two',currency:'ILS'},points:[{date:'2026-10-01',value:50}]});
renderAccountTrend(trend);
assert.match($('accountTrendChart').innerHTML,/stroke="green"/);
assert.doesNotMatch($('accountTrendChart').innerHTML,/stroke="blue"/);

""")


def test_failed_reload_keeps_preview_and_invalid_dates_never_fetch():
    run(BASE + functions('loadReports') + """
let requests=0;
let filters={date_from:'2026-10-30',date_to:'2026-10-01'};
const currentReportFilters=()=>filters;
const valueOf=id=>$(id).value;
const dateValue=()=>'';
const reportQueryParams=()=>'';
const api=async()=>{requests++;throw Error('offline');};
const renderReportSummary=()=>{throw Error('must not replace the preview');};
const renderAccountTrend=renderReportSummary;
const renderHistorySnapshots=renderReportSummary;
const loadTradeHistory=()=>{};
(async()=>{
  await loadReports();
  assert.equal(requests,0);
  assert.match($('reportsExportStatus').textContent,/valid history range/);
  filters={date_from:'2026-10-01',date_to:'2026-10-30'};
  state.activeReport={accounts:1};
  $('reportsDetails').innerHTML='existing preview';
  await assert.rejects(loadReports(),/offline/);
  assert.equal($('reportsDetails').innerHTML,'existing preview');
  assert.match($('reportsExportStatus').textContent,/previous report is still displayed/);
  assert.equal($('loadReports').disabled,false);
  assert.equal($('updateReportHistory').disabled,false);
})().catch(error=>{console.error(error);process.exitCode=1;});
""")


def test_late_response_cannot_replace_a_newer_report():
    run(BASE + functions('loadReports') + """
const currentReportFilters=()=>({date_from:'2026-10-01',date_to:'2026-10-30'});
const valueOf=()=>'';
const dateValue=()=>'';
const reportQueryParams=()=>'';
const pending=[];
const api=()=>new Promise(resolve=>pending.push(resolve));
const renderReportSummary=report=>{$('reportsDetails').innerHTML=String(report.accounts);};
const renderAccountTrend=()=>{};
const renderHistorySnapshots=()=>{};
const loadTradeHistory=()=>{};
(async()=>{
  const older=loadReports();
  const newer=loadReports();
  pending[3]({accounts:2});pending[4]({accounts:[]});pending[5]({items:[]});
  await newer;
  pending[0]({accounts:1});pending[1]({accounts:[]});pending[2]({items:[]});
  await older;
  assert.equal(state.activeReport.accounts,2);
  assert.equal($('reportsDetails').innerHTML,'2');
})().catch(error=>{console.error(error);process.exitCode=1;});
""")


def test_hebrew_mobile_report_labels_are_translated():
    run("const window = {};\n" + (ROOT / 'web/i18n.js').read_text() + """
const assert = require('node:assert/strict');
for (const label of ['Symbol','Name','Asset class','Quantity','Value','P/L on open positions']) {
  assert.notEqual(window.PortfolioI18n.translate(label,'he'), label);
}
""")


def test_blank_history_value_never_posts_but_explicit_zero_does():
    run(BASE + functions('saveHistorySnapshot') + """
const valueOf = id => $(id).value;
let focused = false, writes = [];
$('historyValue').focus = () => { focused = true; };
$('historyAccount').value = 'account';
const api = async (url, options) => { writes.push(JSON.parse(options.body)); };
const clampedHistoryDate = value => value;
const dateValue = () => '2026-10-30';
const loadReports = async () => {};
const loadPortfolio = async () => {};
(async () => {
  await saveHistorySnapshot();
  assert.equal(writes.length, 0);
  assert.equal(focused, true);
  assert.match($('historyStatus').textContent, /Blank values do not replace/);
  $('historyValue').value = '0';
  await saveHistorySnapshot();
  assert.equal(writes.length, 1);
  assert.equal(writes[0].value, '0');
})().catch(error => { console.error(error); process.exitCode = 1; });
""")
