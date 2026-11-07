"""Signed current cash keeps its amount, permissions and distinct visual state."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_cash_sign_states_and_unavailable_are_distinct_for_editors_and_viewers():
    source = (ROOT / 'web/account-cash-ui.js').read_text()
    start = source.index('function accountCashSummaryHtml(')
    end = start + re.search(r'^}', source[start:], re.M).end()
    script = r'''
const assert=require('node:assert/strict');
let editor=true;
const accountNativeCashBalance=a=>a.balance,accountLabel=a=>a.id;
const money=(v,c)=>`${c} ${v.toFixed(2)}`,t=x=>x,esc=x=>String(x),canWrite=()=>editor;
''' + source[start:end] + r'''
for(editor of [true,false]){
 for(const [balance,tone] of [[38819.65,'positive'],[0,'zero'],[-0,'zero'],[-1250.75,'negative'],[null,'unavailable']]){
  const account={id:'account',balance,currency:'USD'};
  const before=JSON.stringify(account),html=accountCashSummaryHtml(account,{compact:true,entry:'dashboard'});
  assert.ok(html.includes(`cash-${tone}`));
  assert.ok(html.includes(balance===null?'Not available':money(balance,'USD')));
  assert.equal(html.includes('data-update-account-cash='),editor);
  assert.equal(JSON.stringify(account),before);
 }
}
'''
    result = subprocess.run(['node'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
