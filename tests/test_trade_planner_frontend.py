from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text() + r'''
const assert = require('node:assert/strict');
window.PortfolioTradePlanner = require('./web/trade-planner.js');
const state = {language:'he',localAccounts:[],localTransactions:[],items:[],fxRates:{}};
const t = text => window.PortfolioI18n.translate(text,state.language);
const esc = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const fmt = n => String(n);
const money = (n,currency) => `${currency} ${n.toFixed(2)}`;
const currencyDisplayLabel = currency => currency;
const formatDate = value => value.slice(0,10).split('-').reverse().join('/');
const formatDateTime = formatDate;
const nodes = {suggestTradeAccount:{disabled:false}};
const $ = id => nodes[id];
const handlers = {};
const document = {querySelectorAll:()=>[],addEventListener:(event,handler)=>handlers[event]=handler};
const riskScoreForItems = () => ({score:10});
const accountHorizonYears = () => 20;
const industryLabel = () => 'Technology';
const volatilityProxy = () => 20;
const derivativeHolding = () => false;
const ctx = {accounts:[{id:'one',account_id:'A1',type:'Investment',location:'USA',currency:'USD',initial_cash:100000}],
 transactions:[],items:[],base_currency:'USD',fx_quotes:[],calculated_at:'2026-10-30T12:00:00Z',
 security:{holding:{symbol:'NEW',currency:'USD',asset_class:'EQUITY',stock_market:'NASDAQ',sector:'Technology'},
 price_ranges:{'1m':{current:100,current_date:'2026-10-29'}}}};
let calls=0, pending=[];
const api = () => {calls++;return new Promise((resolve,reject)=>pending.push({resolve,reject}));};
''' + (ROOT / "web/trade-planner-ui.js").read_text() + "\n" + body
    completed = subprocess.run(["node"], input=script, cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_buy_only_buttons_and_bilingual_results_have_no_raw_operational_labels():
    run_ui('''
const buy={signal:'buy',symbol:'NEW',rule_id:'one'};
assert.ok(tradePlannerSignalAction(buy,0).includes('data-trade-signal'));
assert.equal(tradePlannerSignalAction({...buy,signal:'sell'},0),'');
assert.equal(tradePlannerSignalAction({...buy,signal:'watch'},0),'');
const result=window.PortfolioTradePlanner.plan(ctx,{action:'SHORT',amount:1000},
 {risk:riskScoreForItems,horizon:accountHorizonYears,industry:industryLabel,volatility:volatilityProxy,derivative:derivativeHolding});
assert.equal(result.status,'ok');
for(const language of ['he','en','he']){
 state.language=language;
 const html=tradePlannerResultHtml({status:'ready',result});
 const text=html.replace(/<[^>]*>/g,'');
 assert.ok(text.includes('29/10/2026'));
 assert.ok(!/undefined|NaN/.test(text));
 if(language==='he'){
   assert.ok(text.includes('אומדן מותנה למכירה בחסר'));
   assert.ok(text.includes('דרישות הביטחונות לא אומתו'));
   assert.ok(!/cash|risk|collateral|estimate|short|requested|account|limit|quote|whole|shares|Calculated/i.test(text));
 }else{
   assert.ok(!/[א-ת]/.test(text));
   assert.ok(text.includes('Conditional short estimate'));
 }
}
''')


def test_async_planning_rejects_duplicates_and_late_stale_results_then_recovers():
    run_ui('''
(async()=>{
 const request={symbol:'NEW',action:'BUY',amount:''};
 const first=calculateTradePlan('manual',request);
 assert.equal(tradePlannerViews.get('manual').status,'loading');
 assert.equal(nodes.suggestTradeAccount.disabled,true);
 await calculateTradePlan('manual',request);
 assert.equal(calls,1);
 invalidateTradePlans();
 const second=calculateTradePlan('manual',request);
 assert.equal(calls,2);
 pending[0].resolve(ctx);await first;
 assert.equal(tradePlannerViews.get('manual').status,'loading');
 pending[1].resolve(ctx);await second;
 assert.equal(tradePlannerViews.get('manual').result.status,'ok');
 assert.equal(nodes.suggestTradeAccount.disabled,false);
 const third=calculateTradePlan('manual',request);
 pending[2].reject(new Error('private provider error'));await third;
 assert.equal(tradePlannerViews.get('manual').status,'error');
 assert.ok(!tradePlannerResultHtml(tradePlannerViews.get('manual')).includes('private provider error'));
 resetTradePlannerViews();assert.equal(tradePlannerViews.size,0);
})();
''')
