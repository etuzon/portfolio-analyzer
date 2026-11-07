"""The combined account card keeps distinct account identities and all balances."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_one_card_per_account_joins_risk_by_id_and_keeps_zero_accounts():
    source = (ROOT / 'web/app.js').read_text()
    start = source.index('function renderPortfolioValueDashboard(')
    end = start + re.search(r'^}', source[start:], re.M).end()
    script = r'''
const assert=require('node:assert/strict');
const accounts=[{accountId:'A',account:'Same name',type:'Bank',value:500,currencies:['USD'],localValues:{USD:500}},
 {accountId:'B',account:'Same name',value:200,currencies:['USD'],localValues:{USD:200}},
 {accountId:'Z',account:'Empty account',value:0,currencies:['USD'],localValues:{USD:0}},
 ...['P','K','E','U','R','L','D'].map(id=>({accountId:id,account:id==='L'?'Legacy Pension':id==='D'?'Ambiguous':id,type:id==='U'?undefined:'Investment',value:50,currencies:['USD'],localValues:{USD:50}}))];
const types={A:'Investment',B:'Investment',Z:'Investment',P:'Long-Term Savings',K:'Bank',E:'ESOP'};
const state={portfolioReady:true,baseCurrency:'USD',localAccounts:Object.entries(types).map(([id,type])=>({id,type,currency:'USD'}))};
state.localAccounts.push({id:'legacy-pension',username:'Legacy Pension',type:'Long-Term Savings'},
 {id:'same-investment',username:'Ambiguous',type:'Investment'}, {id:'same-bank',username:'Ambiguous',type:'Bank'});
const riskSource={total:{score:35},accounts:[{key:'B',account:'Same name',risk:{score:82}},
 {key:'A',account:'Same name',risk:{score:17}}]};
const portfolioRiskSnapshot=()=>riskSource;
const sum=xs=>xs.reduce((a,b)=>a+b,0),normalizedField=()=>0,normalizedAmount=v=>v;
const portfolioAccounts=()=>state.localAccounts,accountCashBalance=()=>0,accountNativeCashBalance=()=>0;
const accountLabel=a=>a.username||a.id,cleanSourceLabel=x=>String(x||'').trim(),optionLabel=x=>x,t=x=>x,esc=x=>String(x??'');
const groupByAccount=()=>accounts.map(a=>({...a}));
const accountShareSnapshot=()=>({shares:new Map([['A',71.4],['B',28.6],['Z',0]])});
const money=(v,c)=>`${c} ${v}`,signedMoney=money,fmt=v=>String(v),currencyDisplayLabel=v=>v;
const riskBadge=r=>`<span data-score="${r.score}"></span>`,accountShareBadge=v=>`<span data-share="${v}"></span>`;
const accountCashSummaryHtml=a=>a?`<button data-update-account-cash="${a.id}">cash</button>`:'';
const riskBand=()=>({key:'medium',label:'Moderate'}),riskTooltip=()=>'',renderDataGapsStat=()=>'';
''' + source[start:end] + r'''
const original=JSON.stringify(riskSource);
const html=renderPortfolioValueDashboard([]);
assert.equal((html.match(/data-account-summary=/g)||[]).length,4);
const card=id=>html.split(`data-account-summary="${id}"`)[1].split('</article>')[0];
for(const [id,score,value,share] of [['A',17,500,71.4],['B',82,200,28.6]]){
 assert.ok(card(id).includes(`data-score="${score}"`),id);
 assert.ok(card(id).includes(`USD ${value}`),id);
 assert.ok(card(id).includes(`data-share="${share}"`),id);
 assert.ok(card(id).includes(`data-update-account-cash="${id}"`),id);
 assert.ok(card(id).includes('Account type: Investment'),id);
}
assert.ok(card('Z').includes('USD 0')&&card('Z').includes('data-share="0"'));
assert.ok(html.includes('data-account-summary="R"'),'unlinked imported Investment groups remain visible');
for(const id of ['P','K','E','U','L','D'])assert.ok(!html.includes(`data-account-summary="${id}"`),'exclude '+id);
assert.ok(!card('Z').includes('data-score='),'no fabricated risk on an empty account');
assert.ok(!html.includes('account-risk-allocation-card'));
assert.equal(JSON.stringify(riskSource),original);
'''
    result = subprocess.run(['node'], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_background_redraw_keeps_focused_account_and_its_open_drawer_after_reordering():
    source = (ROOT / 'web/app.js').read_text()
    start = source.index('function preserveRenderedInteraction(')
    end = start + re.search(r'^}', source[start:], re.M).end()
    script = r'''
const assert=require('node:assert/strict');
const document={activeElement:null};
const makeCard=key=>{
 const card={dataset:{accountSummary:key}};
 const summary={tagName:'SUMMARY',className:'',attributes:[],isConnected:true,
  closest:selector=>selector==='[data-account-summary]'?card:null,
  focus:options=>{assert.equal(options.preventScroll,true);document.activeElement=summary;}};
 const details={id:'',className:'risk-data-quality',open:false,closest:()=>card};
 card.querySelectorAll=selector=>selector==='SUMMARY'?[summary]:[details];
 return {card,summary,details};
};
const total={id:'',className:'risk-data-quality',open:false,closest:()=>null};
let a=makeCard('A'),b=makeCard('B');a.details.open=true;
let cards=[a,b];
const root={contains:()=>true,querySelectorAll:selector=>selector==='details'?[total,...cards.map(x=>x.details)]:cards.map(x=>x.card)};
document.activeElement=a.summary;
''' + source[start:end] + r'''
const restore=preserveRenderedInteraction(root);
a.summary.isConnected=false;
const nextA=makeCard('A'),nextB=makeCard('B');
cards=[nextB,nextA];
restore();
assert.equal(document.activeElement,nextA.summary);
assert.equal(nextA.details.open,true);
assert.equal(nextB.details.open,false);
assert.equal(total.open,false);
'''
    result = subprocess.run(['node'], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
