"""Financial risk estimates keep missing-evidence and monetary scope explicit."""
from pathlib import Path
import re
import subprocess

from test_native_account_history_qa import chromium
from test_account_cash_update_qa import browser_wait, cash_browser_document


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    app = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("esc", "riskBand", "riskTooltip", "riskBadge", "sortHoldingsRows"):
        start = app.index(f"function {name}(")
        end = start + re.search(r"^}", app[start:], re.M).end()
        functions.append(app[start:end])
    boot = """
const assert=require('node:assert/strict'),window={},document={addEventListener(){}};
const state={language:'en',baseCurrency:'ILS'};
const optionLabel=text=>window.PortfolioI18n.translate(text,state.language);
const fmt=value=>String(value);
"""
    script = "\n".join([boot, (ROOT / "web/i18n.js").read_text(),
        (ROOT / "web/stress-risk-ui.js").read_text(), *functions, body])
    result = subprocess.run(["node"], input=script, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_asset_aware_money_market_estimate_does_not_display_the_omitted_fund_zero():
    run_ui("""
const risk={model:'portfolio-risk-v4',status:'incomplete',score:null,
 provisional_model:'portfolio-risk-provisional-v3',provisional_basis:'asset_aware_scenarios',
 provisional_scope:'portfolio',provisional_score:1,provisional_loss_pct:.921,provisional_loss:9.21,
 provisional_net_equity:1000,provisional_proxy_gross:921,partial_stress_loss:0,
 provisional_assumptions:[{code:'money_market_proxy',symbol:'5139324',loss_fraction:.01,
 source_date:'2024-09-24',currency_exposures:{ILS:1}},{code:'stale_valuation',symbol:'5139324',source_date:'2026-10-01'}],
 base_currency:'ILS',coverage:{complete:false,covered_value_percent:7.9},
 gaps:[{code:'fund_lookthrough',symbol:'5139324',security_key:'5139324|TASE|ILS'}]};
const original=JSON.stringify(risk);
for(const language of ['en','he']) {
 state.language=language;
 const display=stressRiskDisplay(risk),html=riskBadge(risk),tooltip=riskTooltip(risk),summary=stressRiskSummaryHtml(risk);
 assert.equal(display.number,.921);assert.equal(display.automatic,true);assert.equal(display.ceiling,false);
 assert.ok(html.includes('~0.9%')&&html.includes('⚠')&&html.includes('risk-stress'));
 assert.ok(html.includes(optionLabel('Estimate')));
 assert.ok(tooltip.includes('1.0%')&&tooltip.includes('24/09/2024')&&tooltip.includes('01/10/2026'));
 assert.ok(tooltip.includes('5139324')&&tooltip.includes('9.21'));
 assert.ok(tooltip.includes('ILS 100.0%'));
 assert.ok(!stressRiskScenarioLabel('country_crisis:generic:USD').includes('generic:'));
 assert.ok(summary.includes('9.21')&&!summary.includes('0.00'));
 assert.ok(!tooltip.includes('100% of unmodeled')&&!tooltip.includes('precautionary ceiling'));
 if(language==='he') for(const word of ['Estimate','Money-market','Saved price','Full-model','Additional'])assert.ok(!tooltip.includes(word),word);
}
assert.equal(JSON.stringify(risk),original);
""")


def test_unknown_monetary_scope_uses_a_range_and_only_secondary_known_position_score():
    run_ui("""
const risk={model:'portfolio-risk-v4',status:'incomplete',score:null,
 provisional_model:'portfolio-risk-provisional-v3',provisional_basis:'asset_aware_scenarios',
 provisional_scope:'known_values',provisional_range:{min:0,max:100},provisional_score:0,
 provisional_loss:0,provisional_loss_pct:null,provisional_known_loss_pct:0,provisional_net_equity:100,coverage:{complete:false,covered_value_percent:null},
 gaps:[{code:'valuation',symbol:'MISSING'}]};
for(const language of ['en','he']) {
 state.language=language;
 const display=stressRiskDisplay(risk),html=riskBadge(risk),tooltip=riskTooltip(risk),summary=stressRiskSummaryHtml(risk);
 assert.equal(display.number,null);assert.equal(display.unknownScope,true);
 assert.equal(display.value,optionLabel('Incomplete'));assert.ok(html.includes(optionLabel('Incomplete'))&&html.includes('⚠'));
 assert.ok(!html.includes('0–100'));
 assert.ok(html.includes('risk-incomplete')&&!html.includes('risk-low')&&!html.includes('~100'));
 assert.ok(tooltip.includes('0.0%'));
 assert.ok(!tooltip.includes('/100'));
 assert.ok(tooltip.includes(optionLabel('Uncertain scope')));
 assert.ok(tooltip.includes(optionLabel('Incomplete exposure or pricing inputs prevent a whole-portfolio percentage. Known-position estimates are shown separately.')));
 assert.ok(tooltip.includes(optionLabel('Known positions only: ~{percent}% scenario loss').replace('{percent}','0.0')));
 assert.ok(summary.includes(optionLabel('Incomplete exposure or pricing inputs; review missing risk data.')));
 assert.ok(!summary.includes('0.00'));
 const unsupported={...risk,gaps:[{code:'unsupported_instrument',symbol:'KNOWN-OPTION'}]};
 assert.ok(riskTooltip(unsupported).includes(optionLabel('Incomplete exposure or pricing inputs prevent a whole-portfolio percentage. Known-position estimates are shown separately.')));
 assert.ok(!riskTooltip(unsupported).includes('Unknown monetary weights'));
}
""")


def test_country_proxy_basis_is_explicit_and_localized():
    run_ui("""
const risk={provisional_assumptions:[
 {code:'country_stress_proxy',symbol:'DOMICILE',basis:'issuer_domicile_proxy',currency:'USD'},
 {code:'country_stress_proxy',symbol:'GENERIC',basis:'generic_country_proxy',currency:'ILS'}
]};
for(const language of ['en','he']) {
 state.language=language;
 const lines=stressRiskProxyAssumptionLines(risk).join('\\n');
 assert.ok(lines.includes(optionLabel('Issuer domicile used as a country-exposure proxy')));
 assert.ok(lines.includes(optionLabel('Generic country scenario assumption')));
 assert.ok(!lines.includes('issuer_domicile_proxy')&&!lines.includes('generic_country_proxy'));
 if(language==='he')assert.ok(!lines.includes('Issuer domicile')&&!lines.includes('Generic country'));
}
""")


def test_unsupported_payoff_and_recovery_model_labels_are_explicit_and_localized():
    run_ui("""
const risk={provisional_assumptions:[
 {code:'unknown_asset_proxy',symbol:'KNOWN-OPTION'},
 {code:'recovery_model_required',symbol:'KNOWN-DISTRESSED-DEBT'}
]};
for(const language of ['en','he']) {
 state.language=language;
 const lines=stressRiskProxyAssumptionLines(risk).join('\\n');
 assert.ok(lines.includes(optionLabel('Exposure or payoff model unavailable')));
 assert.ok(lines.includes(optionLabel('Recovery and payoff model required')));
 assert.ok(!lines.includes('unknown_asset_proxy')&&!lines.includes('recovery_model_required'));
 assert.ok(!lines.includes('Unknown asset-class proxy'));
 if(language==='he')assert.ok(!lines.includes('Exposure or payoff')&&!lines.includes('Recovery and payoff'));
}
""")


def test_verified_maturity_bound_remains_a_proxy_and_keeps_retrieval_provenance_separate():
    run_ui("""
const risk={model:'portfolio-risk-v4',status:'incomplete',score:null,
 provisional_model:'portfolio-risk-provisional-v3',provisional_scope:'portfolio',provisional_score:2,provisional_loss_pct:1.5,
 provisional_loss:15,provisional_net_equity:1000,base_currency:'USD',coverage:{complete:false},
 gaps:[{code:'bond_cashflows',symbol:'TREASURY'}],provisional_assumptions:[{
 code:'bond_duration_maturity_bound',symbol:'TREASURY',duration_years:.75,maturity_date:'2027-08-15',
 source_url:'https://www.treasurydirect.gov/TA_WS/securities/search',reference_retrieved_at:'2026-11-14T23:40:00Z'
 }]};
const snapshot=JSON.stringify(risk);
for(const language of ['en','he']) {
 state.language=language;
 const tooltip=riskTooltip(risk),lines=stressRiskProxyAssumptionLines(risk).join('\\n');
 assert.equal(stressRiskDisplay(risk).available,false);
 assert.equal(stressRiskDisplay(risk).automatic,true);
 assert.ok(riskBadge(risk).includes('~1.5%')&&riskBadge(risk).includes('⚠'));
 assert.ok(lines.includes(optionLabel('Sensitivity proxy capped by verified remaining maturity')));
 assert.ok(lines.includes(optionLabel('This bound does not establish actual coupon duration.')));
 assert.ok(lines.includes(optionLabel('Maturity date')+': 15/08/2027'));
 assert.ok(lines.includes(optionLabel('Reference retrieval date')+': 14/11/2026'));
 assert.ok(!lines.includes(optionLabel('Source observation date')));
 assert.ok(!tooltip.includes('2027-08-15')&&!tooltip.includes('2026-11-14T'));
 if(language==='he')assert.ok(!lines.includes('Sensitivity proxy')&&!lines.includes('Reference retrieval'));
}
assert.equal(JSON.stringify(risk),snapshot);
""")


def test_holdings_risk_sort_uses_displayed_points_and_keeps_ranges_last_in_both_languages():
    run_ui("""
const HoldingsSort=require('./web/holdings-sort.js');
const cleanSourceLabel=value=>value,holdingsStatusSortLabel=()=>'',reportAmount=value=>value;
let holdingsTableSort={key:'risk',direction:'asc'};
const row=symbol=>({holding:{symbol,currency:'ILS'}});
const range=row('RANGE'),automatic=row('AUTO2'),verified=row('VERIFIED50'),manual=row('MANUAL35'),missing=row('MISSING'),zero=row('ZERO'),equal=row('EQUAL2'),strong=row('VERIFIED80'),legacy=row('LEGACY10');
const rows=[range,automatic,verified,manual,missing,zero,equal,strong,legacy];
const base={model:'portfolio-risk-v4',score:null,estimated_score:null,provisional_model:'portfolio-risk-provisional-v3',provisional_scope:'portfolio'};
const risks=new Map([
 [range,{...base,provisional_score:99,provisional_known_score:99,provisional_scope:'known_values',provisional_range:{min:0,max:100}}],
 [automatic,{...base,provisional_score:2,provisional_loss_pct:2}],
 [verified,{...base,status:'ok',score:50,loss_pct:50,estimated_score:90,provisional_score:99}],
 [manual,{...base,status:'estimate',estimated_score:35,loss_pct:35,provisional_score:99}],
 [missing,{model:'portfolio-risk-v4',score:null}],
 [zero,{...base,status:'ok',score:0,loss_pct:0,provisional_score:99}],
 [equal,{...base,provisional_score:2,provisional_loss_pct:2}],
 [strong,{...base,status:'ok',score:80,loss_pct:80,estimated_score:10,provisional_score:2}],
 [legacy,{model:'portfolio-risk-v2',score:10}]
]);
state.riskSnapshot={total:{position_risks:risks}};
const snapshot=JSON.stringify({rows,risks:[...risks]});
const symbols=items=>items.map(item=>item.holding.symbol);
for(const language of ['en','he']) {
 state.language=language;
 holdingsTableSort={key:'risk',direction:'asc'};
 assert.deepEqual(symbols(sortHoldingsRows(rows)),['ZERO','AUTO2','EQUAL2','LEGACY10','MANUAL35','VERIFIED50','VERIFIED80','RANGE','MISSING']);
 holdingsTableSort={key:'risk',direction:'desc'};
 assert.deepEqual(symbols(sortHoldingsRows(rows)),['VERIFIED80','VERIFIED50','MANUAL35','LEGACY10','AUTO2','EQUAL2','ZERO','RANGE','MISSING']);
 assert.equal(holdingsTableSort.direction,'desc');
 assert.ok(riskBadge(risks.get(automatic)).includes('~2.0%'));
 assert.ok(riskBadge(risks.get(manual)).includes('~35.0%'));
 assert.ok(riskBadge(risks.get(range)).includes(optionLabel('Incomplete')));
 assert.equal(JSON.stringify({rows,risks:[...risks]}),snapshot);
 holdingsTableSort={key:null,direction:'asc'};
 const original=sortHoldingsRows(rows);assert.deepEqual(original,rows);assert.notEqual(original,rows);
}
""")


def test_saved_v1_result_retains_historical_meaning_and_verified_scores_take_precedence():
    run_ui("""
const legacy={model:'portfolio-risk-v3',status:'incomplete',score:null,
 provisional_model:'portfolio-risk-provisional-v1',provisional_score:100,
 provisional_basis:'missing_valuation_ceiling',provisional_loss:null,
 coverage:{complete:false},gaps:[{code:'valuation'}]};
const tooltip=riskTooltip(legacy);
assert.ok(tooltip.includes('earlier precautionary method'));
assert.equal(stressRiskDisplay(legacy).ceiling,true);
const verified={...legacy,score:25,status:'ok',provisional_model:'portfolio-risk-provisional-v2',
 provisional_score:100,stress_loss:12.5,loss_pct:12.5,net_equity:100,base_currency:'ILS',coverage:{complete:true},gaps:[]};
assert.equal(stressRiskDisplay(verified).number,25);
assert.equal(stressRiskDisplay(verified).automatic,false);
assert.ok(!riskBadge(verified).includes('~100'));
assert.ok(stressRiskSummaryHtml(verified).includes('12.50'));
""")


def test_expanded_rtl_risk_details_repack_before_releasing_dashboard_footprint(tmp_path, chromium):
    """Open evidence must not briefly collapse the page during enrichment redraw."""
    fixture = cash_browser_document(tmp_path, "he")
    app = tmp_path / "cash-app.js"
    app.write_text(app.read_text() + r'''
qa.holdings=[
 {holding:{symbol:'5139324',stock_market:'TASE',currency:'ILS',quantity:1,market_value:921,cost_basis:900,unrealized_profit:21,account_id:'qa-ils',account:'Synthetic ILS cash fund',account_type:'Investment',location:'Israel',asset_class:'MUTUALFUND'},
  exposure_profile:{asset_focus:'money_market',leverage_type:'none',fx_basis:'unhedged',currency_exposures:{ILS:1}},
  stress_risk:{security_key:'5139324|TASE|ILS',valuation_date:'2026-10-01',parameters:{instrument_kind:'fund'}}},
 {holding:{symbol:'QA-BOND',stock_market:'NYSE',currency:'USD',quantity:1,market_value:105,cost_basis:100,unrealized_profit:5,account_id:'qa-usd',account:'Synthetic USD mixed account',account_type:'Investment',location:'USA',asset_class:'BOND'},
  stress_risk:{security_key:'QA-BOND|NYSE|USD',valuation_date:'2026-11-14',parameters:{instrument_kind:'corporate_bond'}}},
 {holding:{symbol:'QA-FUND',stock_market:'NYSE',currency:'USD',quantity:1,market_value:93.4375,cost_basis:90,unrealized_profit:3.4375,account_id:'qa-usd',account:'Synthetic USD mixed account',account_type:'Investment',location:'USA',asset_class:'ETF'},
  exposure_profile:{asset_focus:'broad_equity',leverage_type:'none',fx_basis:'unhedged',currency_exposures:{USD:1}},
  stress_risk:{security_key:'QA-FUND|NYSE|USD',valuation_date:'2026-11-14',parameters:{instrument_kind:'fund'}}}
];
state.localAccounts=[
 {id:'qa-ils',username:'Synthetic ILS cash fund',type:'Investment',currency:'ILS',initial_cash:79,persons:[]},
 {id:'qa-usd',username:'Synthetic USD mixed account',type:'Investment',currency:'USD',initial_cash:114.0625,persons:[]}
];
state.localTransactions=[];state.items=state.allPortfolioItems=qa.holdings;
state.baseCurrency='ILS';state.fxRates={'USD/ILS':3.2};state.riskAsOf='2026-11-14';
state.dashboard=defaultDashboard();
state.dashboard.widgets=state.dashboard.widgets.map(widget=>({...widget,view:widget.id==='portfolio_value'?'basic':'hidden'}));
qa.render=()=>{const restore=preservePortfolioViewport();try{renderAnalytics(qa.holdings);PortfolioI18n.applyToDocument(state.language);}finally{restore();}};
qa.render();PortfolioI18n.observe();qa.fixtureReady=true;
''')
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.fixtureReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    evaluate("qa.details=document.querySelector('[data-account-summary=qa-ils] .stress-risk-gaps');qa.details.open=true;qa.details.querySelector('summary').focus();qa.details.scrollIntoView({block:'center'});")
    settled = "new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))"
    evaluate(settled)
    geometry = r'''(()=>{const summary=document.querySelector('[data-account-summary=qa-ils] .stress-risk-gaps>summary');return {
 y:scrollY,top:summary.getBoundingClientRect().top,doc:document.documentElement.scrollHeight,
 open:summary.parentElement.open,focused:document.activeElement===summary,
 board:$('analyticsBoard').getBoundingClientRect().height};})()'''
    before = evaluate(geometry)
    assert before["open"] and before["focused"] and before["board"] > 700, before
    for _ in range(3):
        evaluate("qa.render()")
        immediate = evaluate(geometry)
        evaluate(settled)
        after = evaluate(geometry)
        for result in (immediate, after):
            assert result["open"] and result["focused"], result
            for field in ("y", "top", "doc", "board"):
                assert abs(before[field] - result[field]) <= 1, (field, before, result)
    assert evaluate("qa.errors") == []
