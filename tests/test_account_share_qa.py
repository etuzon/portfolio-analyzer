"""Independent synthetic QA of account shares in full primary portfolio net value."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _run(assertions):
    source = (ROOT / "web/app.js").read_text()
    names = ('sum', 'normalizedAmount', 'normalizedField', 'cleanSourceLabel', 'accountLabel', 'isEquityCompAccount', 'portfolioAccounts', 'isEquityCompHolding', 'portfolioItems', 'transactionCashImpact', 'accountCashBalance', 'groupByAccount', 'checkedAccountShareAmount', 'accountShareSnapshot')
    functions = []
    for name in names:
        start = re.search(rf'^function {name}\(', source, re.M).start()
        end = re.search(r'^}', source[start:], re.M).end()
        functions.append(source[start:start + end])
    base = r'''
const assert=require('node:assert/strict');
const optionLabel=value=>value;
const state={baseCurrency:'ILS',fxRates:{'USD/ILS':4,'EUR/ILS':5},localTransactions:[],localAccounts:[],items:[]};
const account=(id,currency,initial_cash=0,type='Investment',account_id=id)=>({id,currency,initial_cash,type,account_id});
const holding=(account_id,market_value,currency,extra={})=>({holding:{account_id,account:account_id,market_value,currency,symbol:'QA',asset_class:'EQUITY',...extra}});
const close=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-9,`${actual} != ${expected}`);
const fixture=()=>{
 state.localAccounts=[account('A','USD',25),account('B','EUR',10),account('C','ILS',50),account('ESOP','USD',999999,'ESOP')];
 state.localTransactions=[{account_db_id:'A',action:'BUY',quantity:1,price:50}];
 state.items=[holding('A',100,'USD'),holding('A',100,'ILS'),holding('A',-50,'ILS'),holding('B',50,'EUR'),holding('ESOP',999999,'USD'),holding('A',999999,'USD',{asset_class:'RSU'})];
};
fixture();
'''
    result = subprocess.run(['node'], input=base+'\n'+'\n'.join(functions)+'\n'+assertions, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_uses_all_primary_net_positions_signed_cash_and_converted_currencies():
    _run('''
const value=accountShareSnapshot();
assert.equal(value.available,true);close(value.total,700);
close(value.shares.get('A'),50);close(value.shares.get('B'),300/700*100);close(value.shares.get('C'),50/700*100);
assert.ok(!value.shares.has('ESOP'));
close(value.shares.get('A')+value.shares.get('B')+value.shares.get('C'),100);
''')


def test_visible_filter_subset_cannot_renormalize_full_account_share():
    _run('''
const full=accountShareSnapshot();
const visible=[state.items[0]];
state.filtered=visible;
state.riskSnapshot={accounts:[{key:'A',value:5000}]};
const filtered=accountShareSnapshot();
close(filtered.total,full.total);close(filtered.shares.get('A'),50);
assert.equal(filtered.available,true);
''')


def test_reverse_fx_and_base_currency_changes_keep_percentages_equivalent():
    _run('''
state.fxRates={'ILS/USD':0.25,'ILS/EUR':0.2};
close(accountShareSnapshot().total,700);close(accountShareSnapshot().shares.get('A'),50);
state.baseCurrency='USD';state.fxRates={'ILS/USD':0.25,'EUR/USD':1.25};
close(accountShareSnapshot().total,175);close(accountShareSnapshot().shares.get('A'),50);
''')


def test_negative_accounts_are_signed_and_not_clamped_to_zero_or_100_percent():
    _run('''
state.localTransactions=[];state.localAccounts=[account('short','ILS',-50),account('long','ILS',0)];
state.items=[holding('short',-50,'ILS'),holding('long',200,'ILS')];
const result=accountShareSnapshot();assert.equal(result.available,true);close(result.total,100);
close(result.shares.get('short'),-100);close(result.shares.get('long'),200);
''')


def test_missing_invalid_fx_or_amount_is_unavailable_even_when_positions_offset():
    _run('''
for(const bad of [undefined,null,'',NaN,Infinity,-Infinity,'invalid',true]){
 fixture();state.items[0].holding.market_value=bad;
 assert.equal(accountShareSnapshot().available,false,String(bad));
}
for(const bad of [undefined,null,'',0,-1,NaN,Infinity,'invalid',true]){
 fixture();state.fxRates={'USD/ILS':bad,'EUR/ILS':5};
 assert.equal(accountShareSnapshot().available,false,String(bad));
}
fixture();state.fxRates={'EUR/ILS':5};state.items.push(holding('A',-100,'USD'));
assert.equal(accountShareSnapshot().available,false,'missing FX cannot disappear through offsetting positions');
''')


def test_zero_negative_and_nonfinite_total_are_unavailable():
    _run('''
state.localTransactions=[];state.localAccounts=[account('A','ILS',0)];
for(const amount of [0,-1]){
 state.items=[holding('A',amount,'ILS')];const result=accountShareSnapshot();
 assert.equal(result.available,false);assert.equal(result.total,null);assert.equal(result.shares.size,0);
}
state.items=[holding('A',Number.MAX_VALUE,'ILS'),holding('A',Number.MAX_VALUE,'ILS')];
assert.equal(accountShareSnapshot().available,false);
''')


def test_primary_cash_only_accounts_contribute_even_without_any_holding():
    _run('''
state.localTransactions=[];state.items=[];state.localAccounts=[account('cashA','USD',100),account('cashB','ILS',100),account('employee','USD',999999,'ESOP')];
const result=accountShareSnapshot();assert.equal(result.available,true);close(result.total,500);
close(result.shares.get('cashA'),80);close(result.shares.get('cashB'),20);assert.ok(!result.shares.has('employee'));
''')


def test_account_names_cannot_overwrite_another_accounts_id_share():
    _run('''
state.localTransactions=[];state.localAccounts=[account('A','ILS',0),account('B','ILS',0,'Investment','A')];
state.items=[holding('A',80,'ILS'),holding('B',20,'ILS',{account:'A'})];
const result=accountShareSnapshot();assert.equal(result.available,true);
close(result.shares.get('A'),80);close(result.shares.get('B'),20);
''')
