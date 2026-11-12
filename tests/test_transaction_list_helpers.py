import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script):
    subprocess.run(
        ["node", "-e", "const assert = require('node:assert/strict'); const list = require('./web/transaction-list.js');\n" + script],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )


def test_transaction_filters_find_imported_bonds_without_changing_actions_or_rows():
    run("""
const rows = [
 {id:'sold',symbol:'bond88059ESH8',security_name:'Example Bond',action:'REMOVE',comments:'Imported source SELL transaction',trade_date:'2026-11-12',quantity:3,account_db_id:'a',account_id:'123'},
 {id:'bought',symbol:'bond88059ESH8',action:'BUY',trade_date:'2026-11-11',quantity:8,account_db_id:'b',account_id:'123'},
 {id:'other',symbol:'OTHER',action:'SELL',trade_date:'2026-11-10',quantity:4,account_db_id:'a',account_id:'123'}
];
const before = JSON.stringify(rows);
assert.deepEqual(list.filterAndSort(rows,{query:'BOND88059esh8',action:'SELL'}).map(tx=>tx.id),['sold']);
assert.deepEqual(list.filterAndSort(rows,{action:'REMOVE'}).map(tx=>tx.id),['sold']);
assert.deepEqual(list.filterAndSort(rows,{query:'example transaction',account:list.accountKey(rows[0]),from:'12/11/2026',to:'12/11/2026'}).map(tx=>tx.id),['sold']);
assert.equal(list.filterAndSort(rows,{query:'example absent'}).length,0);
assert.equal(list.accountOptions(rows).length,2);
assert.equal(JSON.stringify(rows),before);
assert.equal(list.displayAction(rows[0]),'SELL');
assert.equal(rows[0].action,'REMOVE');
""")


def test_transaction_sort_is_deterministic_and_missing_values_stay_last():
    run("""
const rows = [
 {id:'a',trade_date:'2026-11-11',created_at:'2026-11-12T10:00:00Z',quantity:4},
 {id:'b',trade_date:'2026-11-12',quantity:2},
 {id:'c',trade_date:'2026-11-11',created_at:'2026-11-12T11:00:00Z',quantity:null},
 {id:'d',trade_date:'bad',quantity:''},
 {id:'e',trade_date:'2026-11-11',created_at:'2026-11-12T11:00:00Z',quantity:10}
];
assert.deepEqual(list.filterAndSort(rows).map(tx=>tx.id),['b','e','c','a','d']);
assert.deepEqual(list.filterAndSort(rows,{sort:'date',direction:'asc'}).map(tx=>tx.id),['a','c','e','b','d']);
assert.deepEqual(list.filterAndSort(rows,{sort:'quantity',direction:'asc'}).map(tx=>tx.id),['b','a','e','c','d']);
assert.deepEqual(list.filterAndSort(rows,{from:'2026-11-12',to:'2026-11-11'}),[]);
assert.equal(list.dateKey('29/02/2024'),'2024-02-29');
assert.equal(list.dateKey('29/02/2025'),'');
assert.equal(list.dateKey('31/04/2026'),'');
assert.equal(list.dateKey('2026-11-12T13:00:00Z'),'2026-11-12');
assert.notEqual(list.defaults(),list.defaults());
""")


def test_transaction_action_sort_uses_visible_labels_and_boolean_quantity_is_missing():
    run("""
const rows = [
 {id:'buy',action:'BUY',quantity:2},
 {id:'sell',action:'REMOVE',comments:'Imported source SELL',quantity:false},
 {id:'short',action:'SHORT',quantity:0}
];
const labels = {BUY:'קנייה',SELL:'מכירה',SHORT:'מכירה בחסר'};
const collator = new Intl.Collator('he',{numeric:true,sensitivity:'base'});
const expected = [...rows].sort((a,b)=>collator.compare(labels[list.displayAction(a)],labels[list.displayAction(b)]));
assert.deepEqual(list.filterAndSort(rows,{sort:'action',direction:'asc',language:'he'},'en',{actionLabel:action=>labels[action]}),expected);
assert.deepEqual(list.filterAndSort(rows,{sort:'quantity',direction:'asc'}).map(tx=>tx.id),['short','buy','sell']);
assert.deepEqual(list.filterAndSort(rows,{sort:'quantity',direction:'desc'}).map(tx=>tx.id),['buy','short','sell']);
""")
