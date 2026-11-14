"""Preserve v2 historical gap evidence; verify v3 gaps are incomplete inputs, not penalties."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_risk(body):
    source = (ROOT / 'web/app.js').read_text()
    names = ('riskStrictBaseValue', 'riskScoreForItems', 'assetRiskFactor', 'derivativeHolding', 'diversifiedFund', 'industryLabel', 'issuerLabel', 'countryLabel', 'economicCurrencyExposure', 'volatilityProxy', 'riskTooltip', 'riskBand')
    functions = []
    for name in names:
        start = source.index(f'function {name}(')
        end = re.search(r'^}', source[start:], re.M).end()
        functions.append(source[start:start+end])
    script = '\n'.join(functions) + '\n' + (ROOT / 'web/risk-data-gaps-ui.js').read_text() + r'''
const assert=require('node:assert/strict');
const PortfolioStressRisk=require('./web/stress-risk.js');
const state={language:'en',baseCurrency:'USD',fxRates:{},riskAsOf:'2026-11-14'};
const sum=values=>values.reduce((a,b)=>a+b,0);
const fmt=value=>String(value);
const clamp=(value,min,max)=>Math.min(max,Math.max(min,value));
const normalizedField=(item,key)=>item.holding[key];
const window={};const document={addEventListener:()=>{}};
''' + (ROOT / 'web/i18n.js').read_text() + r'''
const optionLabel=text=>window.PortfolioI18n.translate(text,state.language);
const stock=(symbol,value=100,currency='USD',asset_class='EQUITY')=>({holding:{symbol,market_value:value,currency,asset_class,stock_market:'NASDAQ',account_id:'account-one',quantity:1,industry:'Technology',sector:'Technology'},industry:'Technology',missing:[],price_ranges:{'1y':{current:100,min:80,high:120}},stress_risk:{valuation_date:'2026-11-14',security_key:symbol+'|NASDAQ|'+currency,issuer_id:symbol,instrument_kind:'equity',country:{country_code:'US',basis:'economic_exposure'},country_rating:{status:'rated',rating:'AAA',scope:'sovereign',scale:'global',term:'long_term',verified:true,source_kind:'agency_public'},currency_exposures:{[currency]:1},parameters:{country_currency:'USD'}}});
// Saved v2 observations carry their own historical component value. This fixture
// exercises the preserved detail renderer, not the current v3 score calculator.
const legacyRisk=(items,{cash=0,dataQuality=0}={})=>({model:'portfolio-risk-v2',score:45,
 components:{data_quality:dataQuality},quality_details:riskMissingDataDetails(items,{totalValue:items.reduce((n,item)=>n+Math.abs(item.holding.market_value),0)+Math.max(0,cash)})});
''' + (ROOT / 'web/stress-risk-ui.js').read_text() + '\n' + body
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_only_actual_risk_input_gaps_are_explained_with_unchanged_score():
    run_risk(r'''
const good=stock('GOOD',100);
const unrelated=stock('FUNDAMENTALS',100);unrelated.missing=['revenue','net income','dividend history'];
assert.deepEqual(riskMissingDataDetails([good,unrelated]),[]);
const prior=riskScoreForItems([good,unrelated],{cash:100,horizonYears:20});
const helper=riskMissingDataDetails;
riskMissingDataDetails=undefined;
const withoutDetails=riskScoreForItems([good,unrelated],{cash:100,horizonYears:20});
riskMissingDataDetails=helper;
assert.equal(prior.score,withoutDetails.score);
assert.deepEqual(prior.components,withoutDetails.components);
assert.equal(prior.model,'portfolio-risk-v3');assert.ok(Number.isFinite(prior.score));assert.equal(prior.components.data_quality,undefined);
assert.equal(prior.quality_details.length,0);
const zero=stock('ZERO',0);zero.missing=['price history'];zero.holding.currency='';zero.holding.asset_class='';
assert.deepEqual(riskMissingDataDetails([zero]),[]);
''')


def test_saved_v2_gap_weights_masks_and_metadata_match_frozen_component():
    run_risk(r'''
const a=stock('AAA',60);a.missing=['price history'];a.industry='';a.holding.industry='';a.holding.sector='';
const b=stock('BBB',40);b.holding.asset_class='';b.holding.currency='';
b.exposure_profile={fx_basis:'reported',currency_exposures:[{currency:'USD',percent:25}]};
const original=JSON.stringify([a,b]);
const risk=legacyRisk([a,b],{cash:100,dataQuality:2.925});
const entries=Object.fromEntries(risk.quality_details.map(detail=>[detail.code,detail]));
assert.equal(entries.price_history.weight_percent,60);assert.equal(entries.price_history.points_before_cap,1.2);
assert.equal(entries.industry.weight_percent,60);assert.ok(Math.abs(entries.industry.points_before_cap-.9)<1e-12);
assert.equal(entries.holding_metadata.weight_percent,40);assert.ok(Math.abs(entries.holding_metadata.points_before_cap-.6)<1e-12);
assert.deepEqual(entries.holding_metadata.affected[0].missing_fields,['currency','asset_class']);
assert.equal(entries.economic_currency.weight_percent,15);assert.ok(Math.abs(entries.economic_currency.points_before_cap-.225)<1e-12);
assert.equal(entries.economic_currency.weight_basis,'total_assets');
assert.equal(entries.price_history.weight_basis,'gross_holdings');
assert.ok(Math.abs(risk.components.data_quality-2.925)<1e-12);
assert.ok(Math.abs(risk.quality_details.reduce((sum,d)=>sum+d.points_before_cap,0)-risk.components.data_quality)<1e-12);
assert.equal(JSON.stringify([a,b]),original);
assert.deepEqual(JSON.parse(JSON.stringify(risk.quality_details)),risk.quality_details);
''')


def test_industry_exemptions_and_overlapping_metadata_are_not_double_counted():
    run_risk(r'''
const instruments=['money_market','government_bond','investment_grade_bond','high_yield_bond'].map((asset_focus,i)=>{const item=stock('EXEMPT'+i,25);item.industry='';item.holding.industry='';item.holding.sector='';item.exposure_profile={asset_focus,fx_basis:'reported',currency_exposures:[{currency:'USD',percent:100}]};return item;});
assert.ok(!riskMissingDataDetails(instruments).some(detail=>detail.code==='industry'));
const missing=stock('BOTH',100);missing.holding.currency='';missing.holding.asset_class='';
const detail=riskMissingDataDetails([missing]).find(detail=>detail.code==='holding_metadata');
assert.equal(detail.weight_percent,100);assert.equal(detail.points_before_cap,1.5);
const all=stock('ALL',100);all.missing=['price history'];all.industry='';all.holding.industry='';all.holding.sector='';all.holding.currency='';all.exposure_profile={fx_basis:'unknown'};
const capped=legacyRisk([all],{cash:0,dataQuality:5});
assert.equal(capped.components.data_quality,5);
assert.ok(capped.quality_details.reduce((total,d)=>total+d.points_before_cap,0)>5);
''')


def test_tooltip_gives_localized_symbol_specific_recovery_and_legacy_safety():
    run_risk(r'''
const item=stock('AAA',100);item.missing=['price history'];item.industry='';item.holding.industry='';item.holding.sector='';item.holding.currency='';item.exposure_profile={fx_basis:'unknown'};
const risk=legacyRisk([item],{cash:100,dataQuality:5});
for(const language of ['en','he','en']){
state.language=language;
const lines=riskMissingDataTooltipLines(risk.quality_details,language).join('\n');
const tip=riskTooltip(risk);
const compact=riskMissingDataTooltipLines(risk.quality_details,language,{compact:true}).join('\n');
assert.ok(tip.includes(compact));assert.ok(!compact.includes('AAA'));
assert.ok(compact.includes(language==='he'?'הרחיבו':'Expand Missing data'));
assert.ok(compact.split('\n').length<=6);
if(language==='en'){assert.ok(lines.includes('not a count'));assert.ok(lines.includes('Prices'));assert.ok(lines.includes('Classify security'));assert.ok(lines.includes('Edit exposure'));assert.ok(!/[א-ת]/.test(lines));}
else{assert.ok(lines.includes('ולא מספר השדות'));assert.ok(lines.includes('במחירים'));assert.ok(lines.includes('סיווג נייר ערך'));assert.ok(!/[a-z]/i.test(lines.replaceAll('AAA','')));}
assert.ok(!/undefined|NaN|null/.test(lines));
}
assert.deepEqual(riskMissingDataTooltipLines(undefined,'he'),[]);
assert.deepEqual(riskMissingDataTooltipLines([{code:'future_version',weight_percent:10}],'en'),[]);
''')



def test_visible_disclosure_is_keyboard_native_safe_and_keeps_all_symbols():
    run_risk(r'''
const items=Array.from({length:14},(_,index)=>{const item=stock('SYM'+index,100);item.missing=['price history'];return item;});
items[0].holding.symbol='<img src=x onerror=evil()>"';
const risk=legacyRisk(items,{cash:0,dataQuality:2});
for(const language of ['en','he']){
 state.language=language;
 const html=riskDataQualityHtml(risk);
 assert.ok(html.startsWith('<details'));assert.ok(html.includes('<summary>'));
 assert.ok(html.includes('tabindex="0" role="region"'));
 assert.ok(html.includes('SYM13'));assert.ok(html.includes('&lt;img src=x onerror=evil()&gt;&quot;'));
 assert.ok(!html.includes('<img'));
 assert.ok(html.includes(language==='he'?'נתונים חסרים':'Missing data'));
 const legacy=riskDataQualityHtml({components:{data_quality:2}});
 assert.ok(legacy.includes(language==='he'?'לא נשמר':'not saved'));
}
assert.equal(riskDataQualityHtml({components:{data_quality:0}}),'');
assert.equal(riskDataQualityHtml(null),'');
''')



def test_v3_missing_inputs_preserve_value_coverage_without_a_missing_data_penalty():
    run_risk(r'''
const known=stock('KNOWN',100),unknown=stock('UNKNOWN',100);
delete unknown.stress_risk.issuer_id;
const before=JSON.stringify([known,unknown]);
const risk=riskScoreForItems([known,unknown],{cash:100,horizonYears:20});
assert.equal(risk.model,'portfolio-risk-v3');assert.equal(risk.score,null);
assert.equal(risk.estimated_score,null);assert.equal(risk.coverage.complete,false);
assert.ok(Math.abs(risk.coverage.covered_value_percent-200/3)<1e-9);
assert.ok(risk.gaps.some(gap=>gap.code==='issuer_identity'&&gap.symbol==='UNKNOWN'));
assert.equal(risk.components.data_quality,undefined);assert.deepEqual(risk.quality_details,[]);
for(const language of ['en','he']) {
 state.language=language;
 const html=riskDataQualityHtml(risk);
 assert.ok(html.startsWith('<details'));assert.ok(html.includes('<summary>'));
 assert.ok(html.includes('UNKNOWN'));assert.ok(!html.includes('/5'));
 const tooltip=riskTooltip(risk);
 assert.ok(tooltip.includes(language==='he'?'נתונים חלקיים':'Partial data'));
 assert.ok(tooltip.includes('~'+risk.provisional_score));
 assert.ok(tooltip.includes('UNKNOWN'));
 assert.ok(!tooltip.includes('NaN')&&!tooltip.includes('undefined'));
}
assert.equal(JSON.stringify([known,unknown]),before);
''')
