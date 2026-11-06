"""Independent display checks; Node measurements are fixtures, not browser QA."""
import json
import subprocess
from pathlib import Path

from app.metrics import trend_from_reports
from test_shared_cash_risk_qa import app_functions
from test_heatmap_frontend import run_ui

ROOT=Path(__file__).resolve().parents[1]


def test_net_income_uses_raw_latest_annual_periods_and_localized_signed_percentage():
    raw=[{'fiscalDateEnding':'2022-12-31','netIncome':-100},
         {'fiscalDateEnding':'2025-12-31','netIncome':-50}]
    trend=trend_from_reports(raw,['netIncome'],'profit')
    assert trend.percent_change==50
    zero=trend_from_reports([{'fiscalDateEnding':'2022-12-31','netIncome':0},
                            {'fiscalDateEnding':'2025-12-31','netIncome':50}],['netIncome'],'profit')
    assert zero.percent_change is None
    setup="const window={};\n"+(ROOT/'web/i18n.js').read_text()+r'''
const assert=require('node:assert/strict');
const state={language:'en'};
const t=value=>window.PortfolioI18n.translate(value,state.language);
const locale=()=>state.language==='he'?'he-IL':'en-US';
const esc=value=>String(value).replaceAll('<','&lt;').replaceAll('>','&gt;');
const formatDate=value=>value.split('-').reverse().join('/');
const formatMetricValue=value=>String(value);
const compactMoney=value=>String(value);
'''
    script=setup+app_functions('trendCell','analyticsStateCell','seriesDate','changeClass','changeText','fmt','pct')
    script+='\nconst source='+json.dumps(trend.__dict__)+';\nconst unknown='+json.dumps(zero.__dict__)+';\n'+r'''
const before=JSON.stringify(source);
for(const language of ['en','he','en']){
 state.language=language;
 const html=trendCell(source,'Net income',{displayPercent:true});
 assert.ok(html.includes('metric-pill up'));
 assert.ok(html.includes('<bdi dir="ltr">+50%</bdi>'));
 assert.ok(html.includes('31/12/2022'));assert.ok(html.includes('31/12/2025'));
 assert.ok(!html.includes('YoY'));
 const unavailable=trendCell(unknown,'Net income',{displayPercent:true});
 assert.ok(unavailable.includes('metric-pill warn'));
 assert.ok(unavailable.includes(language==='he'?'לא זמין':'Not available'));
 assert.ok(!unavailable.includes('>0%<'));
}
assert.equal(JSON.stringify(source),before);
'''
    result=subprocess.run(['node'],input=script,text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stderr


def test_heatmap_type_icons_stay_unboxed_without_visible_type_labels():
    run_ui("globalThis.window={};\n"+(ROOT/'web/i18n.js').read_text()+r'''
// Use the application dictionary where this isolated fixture normally has identity translation.
heatmapText=text=>state.language==='he'?(HEATMAP_HE[text]||window.PortfolioI18n.translate(text,'he')):text;
seed();
const original=JSON.stringify(heatmapView.data);
for(const language of ['en','he']){
 state.language=language;
 for(const [asset_class,label] of [['BOND',language==='he'?'אג״ח':'Bond'],['ETF',language==='he'?'קרן סל':'ETF'],['MUTUALFUND',language==='he'?'קרן':'Fund']]){
  const asset={...a,asset_class};
  const html=heatmapTileMap([asset]);
  assert.ok(!html.includes('class="heatmap-tile-type"'));
  assert.ok(!html.includes(`<span>${label}</span>`));
  assert.ok(html.includes(`<title>${label}</title>`));
  assert.equal((html.match(/class="heatmap-type-icon"/g)||[]).length,1);
  assert.ok(html.includes('₪ 6000.00'));assert.ok(html.includes('+10.00%'));
  assert.ok(html.includes('aria-label='));assert.ok(html.includes('aria-hidden="true"'));
 }
 assert.ok(!heatmapTileMap([a]).includes('class="heatmap-tile-type"'));
}
assert.equal(JSON.stringify(heatmapView.data),original);
const button={clientWidth:140,clientHeight:100,dataset:{},style:{setProperty(){}},querySelector(selector){
 if(selector==='.heatmap-tile-label')return {scrollWidth:140,scrollHeight:60};
 return {clientWidth:120,scrollWidth:selector==='.heatmap-tile-type'?200:100};
}};
heatmapFitLabel(button);
// Existing price/value information fits without an extra type-label row.
assert.equal(button.dataset.heatmapLabelMode,'full');
''')
