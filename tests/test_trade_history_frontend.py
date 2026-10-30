import json
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
    completed = subprocess.run(['node'], input=script, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout) if completed.stdout else None


def test_trade_history_filters_keep_closed_positions_and_reopened_periods():
    run(functions('filteredTradeHistoryItems') + """
const assert=require('node:assert/strict');
const nodes={tradeHistoryPositionStatus:{value:'all'},tradeHistorySearch:{value:''}};
const valueOf=id=>nodes[id].value;
const formatDate=value=>value.split('-').reverse().join('/');
const state={tradeHistory:{items:[
 {id:'old',symbol:'ABC',name:'Alpha',account_label:'Account A',status:'closed',opened_date:'2025-01-01',closed_date:'2025-12-30'},
 {id:'new',symbol:'ABC',name:'Alpha',account_label:'Account A',status:'open',opened_date:'2026-01-01'},
 {id:'other',symbol:'DEF',name:'Delta',account_label:'Account B',status:'closed',opened_date:'2026-02-01',closed_date:'2026-03-01'}]}};
assert.equal(filteredTradeHistoryItems().length,3);
nodes.tradeHistoryPositionStatus.value='closed';
assert.deepEqual(filteredTradeHistoryItems().map(row=>row.id),['old','other']);
nodes.tradeHistorySearch.value='alpha';
assert.deepEqual(filteredTradeHistoryItems().map(row=>row.id),['old']);
nodes.tradeHistorySearch.value='30/12/2025';
assert.deepEqual(filteredTradeHistoryItems().map(row=>row.id),['old']);
""")


def test_csv_preserves_numeric_losses_and_neutralizes_formula_text():
    run(functions('tradeHistoryCsvCell') + r"""
const assert=require('node:assert/strict');
assert.equal(tradeHistoryCsvCell(-12.34),'"-12.34"');
assert.equal(tradeHistoryCsvCell(null),'""');
assert.equal(tradeHistoryCsvCell('=HYPERLINK("bad")'),'"\'=HYPERLINK(""bad"")"');
assert.equal(tradeHistoryCsvCell(' +SUM(A1)'),'"\' +SUM(A1)"');
assert.equal(tradeHistoryCsvCell('Account, A'),'"Account, A"');
""")


def test_operational_history_states_and_actions_are_localized():
    labels = [
        'Loading recorded trade history…', 'Could not load trade history. Retry to load this section.',
        'Open position', 'Closed position', 'Holding periods', 'Saved local prices',
        'Realized P/L', 'Unrealized P/L', 'Total P/L', 'P/L per day', 'P/L per year',
        'Purchase date unavailable — imported position snapshot',
        'Daily and yearly P/L are unavailable for a same-day position',
        'Some history data is incomplete', 'Retry', 'Details', 'Limited data',
        'Buy', 'Sell', 'Add', 'Remove', 'Short', 'Dividend', 'Interest', 'Fee',
    ]
    result = run('const window={};\n' + (ROOT / 'web/i18n.js').read_text() + '\nconst labels=' + json.dumps(labels) + ";process.stdout.write(JSON.stringify(labels.map(label=>window.PortfolioI18n.translate(label,'he'))));")
    assert all(re.search(r'[א-ת]', label) for label in result)
    assert all(not re.search(r'[A-Za-z]', label) for label in result)


def test_late_history_response_cannot_replace_newer_scope_and_failure_is_local():
    run(functions('loadTradeHistory') + """
const assert=require('node:assert/strict');
const state={};const requests=[];let renders=0;
const renderTradeHistory=()=>{renders++;};
const reportQueryParams=filters=>filters.account_id;
const api=url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject}));
(async()=>{
 const older=loadTradeHistory({account_id:'old'});
 const newer=loadTradeHistory({account_id:'new'});
 requests[1].resolve({items:[{id:'new'}]});await newer;
 requests[0].resolve({items:[{id:'old'}]});await older;
 assert.equal(state.tradeHistory.items[0].id,'new');
 assert.equal(state.tradeHistoryLoading,false);
 const failure=loadTradeHistory({account_id:'third'});
 requests[2].reject(Error('offline'));await failure;
 assert.equal(state.tradeHistory,null);
 assert.equal(state.tradeHistoryError,true);
 assert.equal(state.tradeHistoryLoading,false);
 assert.ok(renders>=4);
})().catch(error=>{console.error(error);process.exitCode=1;});
""")
